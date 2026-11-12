"""Server-owned PKS generation and immutable signed-file archives."""
import uuid
from datetime import datetime, timezone
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from admin_reports import fingerprint, request_id
import pks_document

class DraftInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    officer_id:str=Field(min_length=1,max_length=100)
    duration:int=Field(ge=1,le=600,strict=True)
    unit:str=Field(pattern='^(BULAN|TAHUN)$')

class GenerateInput(DraftInput):
    submission_id:str=Field(min_length=1,max_length=100)

def register(router,runtime,agreements):
    async def source(data,user):
        officer=await runtime.db.users.find_one({'id':data.officer_id,'company_id':user['company_id'],'role':'petugas'})
        if not officer:raise HTTPException(404,'Petugas tidak ditemukan.')
        if officer.get('status')=='nonaktif':raise HTTPException(400,'Petugas nonaktif tidak dapat dibuatkan PKS baru.')
        company=await runtime.db.companies.find_one({'id':user['company_id']}) or {}
        dates=agreements.period(data.duration,data.unit)
        return pks_document.snapshot(company,officer,dates,data.duration,data.unit)

    @router.post('/pks/preview')
    async def preview(data:DraftInput,user:dict=Depends(runtime.admin_required)):
        frozen=await source(data,user)
        content=await run_in_threadpool(pks_document.render,frozen)
        return Response(content,media_type='application/pdf',headers={'Content-Disposition':'inline; filename="Preview-PKS.pdf"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/pks/generate')
    async def generate(data:GenerateInput,request:Request,user:dict=Depends(runtime.admin_required)):
        key=request_id(data.submission_id)
        identity=str(uuid.uuid5(uuid.NAMESPACE_URL,f"pks-generated:{user['company_id']}:{key}"))
        scope={'id':identity,'company_id':user['company_id'],'kind':'pks'}
        digest=fingerprint([data.officer_id,data.duration,data.unit,'generated'],[])
        def cached(record):
            if record.get('fingerprint')!=digest:raise HTTPException(409,'ID pengiriman sudah digunakan untuk PKS berbeda. Muat ulang formulir.')
            return agreements.public(record)
        existing=await runtime.db.documents.find_one(scope)
        if existing:return cached(existing)
        # Validate before creating upload intents or consuming a document number.
        await source(data,user)
        path=f"{runtime.APP_NAME}/companies/{user['company_id']}/pks/{identity}/{runtime.new_id()}.pdf"
        await runtime.db.upload_intents.insert_one({'id':path,'company_id':user['company_id'],'storage_path':path,'created_at':datetime.now(timezone.utc)})
        async def commit():
            # Serialize generation with officer deletion and other PKS submissions.
            officer=await runtime.db.users.find_one_and_update({'id':data.officer_id,'company_id':user['company_id'],'role':'petugas'},{'$inc':{'relation_version':1}},return_document=True)
            if not officer:raise HTTPException(404,'Petugas tidak ditemukan.')
            existing=await runtime.db.documents.find_one(scope)
            if existing:return cached(existing)
            frozen=await source(data,user)
            year=int(frozen['start_date'][:4]);month=int(frozen['start_date'][5:7])
            sequence=await runtime.next_sequence(f"pks_{user['company_id']}_{year}")
            number=f'{sequence:03d}/PKSM/{pks_document.ROMAN[month-1]}/{year}'
            # The saved numbered PDF is ready to print/sign; draft status stays in the UI.
            content=await run_in_threadpool(pks_document.render,frozen,number,False)
            await run_in_threadpool(runtime.validate_pdf,content)
            await run_in_threadpool(runtime.put_object,path,content,'application/pdf')
            record={**scope,'officer_id':data.officer_id,'officer_name':frozen['officer']['name'],'officer_code':frozen['officer']['petugas_code'],'start_date':frozen['start_date'],'end_date':frozen['end_date'],'duration':data.duration,'duration_unit':data.unit,'created_at':runtime.now_iso(),'created_by':user['id'],'document_number':number,'document_status':'DRAFT','source':'GENERATED','document_snapshot':frozen,'filename':f'PKS-{sequence:03d}-{year}.pdf','url':'/api/files/'+path,'storage_path':path,'fingerprint':digest}
            await runtime.db.documents.insert_one(dict(record))
            await runtime.db.upload_intents.delete_one({'id':path,'company_id':user['company_id']})
            await runtime.log_audit(user,'Membuat draft PKS otomatis','pks',identity,request)
            return agreements.public(record)
        return await runtime.transactions.run(runtime.client,commit)

    @router.post('/pks/{identity}/signed')
    async def signed(identity:str,request:Request,submission_id:str=Form(...),file:UploadFile=File(...),user:dict=Depends(runtime.admin_required)):
        key=request_id(submission_id);scope={'id':identity,'company_id':user['company_id'],'kind':'pks'}
        record=await runtime.db.documents.find_one(scope)
        if not record:raise HTTPException(404,'PKS tidak ditemukan.')
        if record.get('source')!='GENERATED':raise HTTPException(400,'Unggahan arsip tanda tangan tersedia untuk PKS yang dibuat otomatis.')
        if file.content_type!='application/pdf':raise HTTPException(400,'Arsip PKS harus berupa PDF, maksimal 8 MB.')
        content=await file.read(runtime.MAX_FILE_SIZE+1)
        if not content or len(content)>runtime.MAX_FILE_SIZE:raise HTTPException(400,'Arsip PDF wajib diisi dan maksimal 8 MB.')
        try:await run_in_threadpool(runtime.validate_pdf,content)
        except Exception:raise HTTPException(400,'PDF arsip tidak valid, terkunci, atau mengandung konten aktif.')
        digest=fingerprint([identity],[{'kind':'pks_signed','name':'signed.pdf','content':content}])
        def cached(current):
            if current.get('signed_submission_id')==key and current.get('signed_fingerprint')==digest:return agreements.public(current)
            raise HTTPException(409,'PKS ini sudah memiliki arsip tanda tangan. Dokumen sebelumnya tidak ditimpa.')
        if record.get('signed_url'):return cached(record)
        attachment_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f"pks-signed:{user['company_id']}:{identity}:{key}"))
        path=f"{runtime.APP_NAME}/companies/{user['company_id']}/pks/{identity}/signed-{runtime.new_id()}.pdf"
        await runtime.db.upload_intents.insert_one({'id':path,'company_id':user['company_id'],'storage_path':path,'created_at':datetime.now(timezone.utc)})
        await run_in_threadpool(runtime.put_object,path,content,'application/pdf')
        async def commit():
            current=await runtime.db.documents.find_one_and_update(scope,{'$inc':{'relation_version':1}},return_document=True)
            if not current:raise HTTPException(404,'PKS tidak ditemukan.')
            if current.get('signed_url'):return cached(current)
            attachment={'id':attachment_id,'company_id':user['company_id'],'kind':'pks_signed','pks_id':identity,'storage_path':path,'url':'/api/files/'+path,'filename':f"PKS-ditandatangani-{identity}.pdf",'created_at':runtime.now_iso(),'created_by':user['id']}
            await runtime.db.documents.insert_one(attachment)
            update={'signed_url':attachment['url'],'signed_at':runtime.now_iso(),'signed_by':user['id'],'signed_submission_id':key,'signed_fingerprint':digest,'document_status':'SIGNED_ARCHIVED'}
            await runtime.db.documents.update_one(scope,{'$set':update})
            await runtime.db.upload_intents.delete_one({'id':path,'company_id':user['company_id']})
            await runtime.log_audit(user,'Mengarsipkan PKS ditandatangani','pks',identity,request)
            return agreements.public({**current,**update})
        return await runtime.transactions.run(runtime.client,commit)
