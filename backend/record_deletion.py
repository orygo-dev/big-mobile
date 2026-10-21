"""Scoped correction deletes with transactional audit and deferred file cleanup."""
from datetime import datetime, timezone
from fastapi import Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field


class DeletionInput(BaseModel):
    reason: str = Field(default='Koreksi kesalahan input', min_length=3, max_length=500)


async def audit(runtime, user, request, entity, record, reason):
    if len(reason.strip())<3:raise HTTPException(422,'Alasan penghapusan minimal 3 karakter')
    await runtime.db.idempotency.update_many({'company_id':user['company_id'],'$or':[{'response.id':record['id']},{'response.assignment_id':record['id']}]},{'$set':{'deleted':True}})
    # Keep correction evidence, never credentials or arbitrary user payloads.
    keys=('id','nomor','document_number','assignment_number','assignment_id','account_id','client_id','petugas_id','petugas_ids','officer_ids','officer_id','name','email','nama_perusahaan','nama_debitur','nomor_kontrak','leasing_name','officer_name','team_names','payment_amount','payment_status','created_at','payment_recorded_at','status')
    await runtime.db.audit_logs.insert_one({'id':runtime.new_id(),'company_id':user['company_id'],'user_id':user['id'],'user_name':user.get('name',''),'activity':f'Menghapus {entity}: {reason.strip()}','entity':entity,'entity_id':record['id'],'timestamp':runtime.now_iso(),'ip_address':request.client.host if request.client else None,'deletion_reason':reason.strip(),'deleted_data':{key:record[key] for key in keys if key in record}})


async def cleanup(runtime, user, files):
    for item in files:
        path=item.get('storage_path')
        if path and path.startswith(f"{runtime.APP_NAME}/companies/{user['company_id']}/"):
            await runtime.db.upload_intents.update_one({'id':path,'company_id':user['company_id']},{'$set':{'storage_path':path,'created_at':datetime.now(timezone.utc)}},upsert=True)


async def cancel_notifications(runtime, user, entity_id):
    await runtime.db.whatsapp_notifications.update_many({'company_id':user['company_id'],'entity_id':entity_id,'status':{'$in':['PENDING','FAILED']}},{'$set':{'status':'SKIPPED','error':'Record asal dihapus oleh admin/owner.','updated_at':runtime.now_iso()}})


def register(router, runtime):
    async def remove_assignment(identity, request, data, user):
        assignment=await runtime.db.assignments.find_one({'id':identity,'company_id':user['company_id']})
        if not assignment:raise HTTPException(404,'Penugasan tidak ditemukan')
        scope={'assignment_id':identity,'company_id':user['company_id']}
        report_scope={'company_id':user['company_id'],'$or':[{'assignment_id':identity},{'assignment_letter_id':assignment.get('assignment_letter_id') or '__none__'}]}
        if await runtime.db.field_reports.find_one(report_scope):raise HTTPException(409,'Penugasan memiliki laporan lapangan. Hapus laporan yang salah melalui menu Laporan Lapangan terlebih dahulu, lalu hapus penugasan.')
        letters=await runtime.db.assignment_letters.find({'company_id':user['company_id'],'$or':[{'assignment_id':identity},{'id':assignment.get('assignment_letter_id') or '__none__'}]}).to_list(None)
        messages=await runtime.db.chat_messages.find(scope).to_list(None)
        await audit(runtime,user,request,'penugasan',{**assignment,'document_number':', '.join(letter.get('document_number') or letter.get('nomor','') for letter in letters)},(data or DeletionInput()).reason)
        await cleanup(runtime,user,[attachment for message in messages for attachment in message.get('attachments',[])])
        for letter in letters:
            await runtime.db.assignment_letters.delete_one({'id':letter['id'],'company_id':user['company_id']})
        await runtime.db.chat_messages.delete_many(scope)
        await runtime.db.chat_reads.delete_many(scope)
        await cancel_notifications(runtime,user,identity)
        await runtime.db.accounts.update_many({'id':assignment['account_id'],'company_id':user['company_id'],'active_assignment_id':identity},{'$set':{'status':'BELUM_DITUGASKAN','updated_at':runtime.now_iso()},'$unset':{'active_assignment_id':''}})
        other=await runtime.db.assignments.find_one({'company_id':user['company_id'],'account_id':assignment['account_id'],'id':{'$ne':identity},'status':{'$in':['AKTIF','MENUNGGU_APPROVAL']}})
        if not other:
            await runtime.db.accounts.update_many({'id':assignment['account_id'],'company_id':user['company_id'],'active_assignment_id':None,'status':'DITUGASKAN'},{'$set':{'status':'BELUM_DITUGASKAN','updated_at':runtime.now_iso()}})
        await runtime.db.assignments.delete_one({'id':identity,'company_id':user['company_id']})
        return {'ok':True}

    @router.post('/penugasan/{identity}/delete')
    @router.delete('/penugasan/{identity}')
    @runtime.transactional
    async def delete_assignment(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.admin_required)):
        return await remove_assignment(identity,request,data,user)

    @router.post('/surat-tugas/{identity}/delete')
    @router.delete('/surat-tugas/{identity}')
    @runtime.transactional
    async def delete_letter(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.admin_required)):
        letter=await runtime.db.assignment_letters.find_one({'id':identity,'company_id':user['company_id']})
        if not letter:raise HTTPException(404,'Surat tugas tidak ditemukan')
        if letter.get('assignment_id'):
            return await remove_assignment(letter['assignment_id'],request,data,user)
        if await runtime.db.field_reports.find_one({'assignment_letter_id':identity,'company_id':user['company_id']}):raise HTTPException(409,'Hapus laporan terkait yang salah terlebih dahulu.')
        await audit(runtime,user,request,'surat tugas',letter,(data or DeletionInput()).reason)
        await runtime.db.assignment_letters.delete_one({'id':identity,'company_id':user['company_id']})
        return {'ok':True}

    @router.post('/laporan/{identity}/delete')
    @router.delete('/laporan/{identity}')
    @runtime.transactional
    async def delete_report(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.admin_required)):
        scope={'id':identity,'company_id':user['company_id']}
        report=await runtime.db.field_reports.find_one(scope)
        if not report:raise HTTPException(404,'Laporan tidak ditemukan')
        assignment=await runtime.db.assignments.find_one({'id':report.get('assignment_id'),'company_id':user['company_id']}) or {}
        account=await runtime.db.accounts.find_one({'id':report.get('account_id'),'company_id':user['company_id']}) or {}
        expected=runtime.ACCOUNT_STATUS_MAP.get(report.get('status')) if report.get('status')!='LAINNYA' else None
        if expected and account.get('status')==expected and account.get('active_assignment_id')==report.get('assignment_id'):
            restore=(report.get('account_snapshot') or {}).get('status') or 'DITUGASKAN'
            await runtime.db.accounts.update_one({'id':account['id'],'company_id':user['company_id'],'active_assignment_id':report['assignment_id'],'status':expected},{'$set':{'status':restore,'updated_at':runtime.now_iso()}})
        await audit(runtime,user,request,'laporan lapangan',report,(data or DeletionInput()).reason)
        photo_scope={'report_id':identity,'$or':[{'company_id':user['company_id']},{'company_id':None}]}
        photos=await runtime.db.report_photos.find(photo_scope).to_list(None)
        await cleanup(runtime,user,photos)
        await runtime.db.report_photos.delete_many(photo_scope)
        await cancel_notifications(runtime,user,identity)
        await runtime.db.field_reports.delete_one(scope)
        return {'ok':True}

    async def delete_document(identity,kind,request,data,user):
        scope={'id':identity,'company_id':user['company_id'],'kind':kind}
        record=await runtime.db.documents.find_one(scope)
        if not record:raise HTTPException(404,'Data tidak ditemukan')
        await audit(runtime,user,request,'pembayaran leasing' if kind=='leasing_payment' else 'PKS',record,(data or DeletionInput()).reason)
        await cleanup(runtime,user,[record])
        await runtime.db.documents.delete_one(scope)
        return {'ok':True}

    @router.post('/leasing-payments/{identity}/delete')
    @router.delete('/leasing-payments/{identity}')
    @runtime.transactional
    async def delete_payment(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.admin_required)):
        return await delete_document(identity,'leasing_payment',request,data,user)

    @router.post('/pks/{identity}/delete')
    @router.delete('/pks/{identity}')
    @runtime.transactional
    async def delete_pks(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.admin_required)):
        return await delete_document(identity,'pks',request,data,user)

    @router.post('/admin-users/{identity}/delete')
    @router.delete('/admin-users/{identity}')
    @runtime.transactional
    async def delete_admin(identity:str, request:Request, data:DeletionInput=Body(default=None), user:dict=Depends(runtime.owner_required)):
        scope={'id':identity,'company_id':user['company_id'],'role':'admin'}
        record=await runtime.db.users.find_one(scope)
        if not record:raise HTTPException(404,'Pengguna admin tidak ditemukan')
        await audit(runtime,user,request,'pengguna admin',record,(data or DeletionInput()).reason)
        await runtime.db.users.delete_one(scope)
        return {'ok':True}
