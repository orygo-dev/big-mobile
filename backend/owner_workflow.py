"""Owner-only approvals and administrator provisioning; shared monthly cash totals."""
import copy
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from finance import date_bounds
from assignment_team import member_ids


class AdminInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)


def register(router, runtime):
    @router.get('/approvals/pending-count')
    async def pending_count(user: dict = Depends(runtime.owner_required)):
        return {'count':await runtime.db.assignments.count_documents({'company_id':user['company_id'],'status':runtime.ASSIGNMENT_PENDING})}

    @router.post('/penugasan/{assignment_id}/approve')
    @runtime.transactional
    async def approve(assignment_id: str, request: Request, user: dict = Depends(runtime.owner_required)):
        scope={'company_id':user['company_id'],'assignment_id':assignment_id}
        letter=await runtime.db.assignment_letters.find_one(scope)
        if not letter:raise HTTPException(404,'Penugasan tidak ditemukan')
        assignment=await runtime.db.assignments.find_one({'id':assignment_id,'company_id':user['company_id']})
        if not assignment:raise HTTPException(404,'Penugasan tidak ditemukan')
        if letter.get('approval_status')=='APPROVED' and assignment.get('approval_status')=='APPROVED':
            return await runtime.enrich_letter(runtime.clean(letter))
        if not letter.get('approval_required') or letter.get('status')!='menunggu_approval' or assignment.get('status')!=runtime.ASSIGNMENT_PENDING:
            raise HTTPException(409,'Penugasan tidak lagi menunggu approval. Muat ulang data.')
        today=datetime.now(timezone(timedelta(hours=7))).date()
        start,end=runtime.validate_assignment_dates(assignment.get('valid_from'),assignment.get('valid_until'))
        if end and end<today:raise HTTPException(409,'Masa penugasan telah berakhir. Batalkan dan buat penugasan baru.')
        sk=await runtime.db.power_of_attorneys.find_one({'id':assignment['power_of_attorney_id'],'company_id':user['company_id']})
        client=await runtime.db.clients.find_one({'id':assignment['client_id'],'company_id':user['company_id']})
        if not sk or sk.get('status')!='aktif' or not client or client.get('status','aktif')!='aktif':
            raise HTTPException(409,'Surat Kuasa atau leasing tidak aktif')
        sk_start,sk_end=runtime.validate_assignment_dates(sk.get('tanggal_berlaku'),sk.get('tanggal_berakhir'))
        if (sk_end and (sk_end<today or (end and end>sk_end) or (start and start>sk_end))) or (sk_start and start and start<sk_start):
            raise HTTPException(409,'Masa penugasan tidak sesuai masa Surat Kuasa')
        for identity in member_ids(assignment):
            if not await runtime.db.users.find_one({'id':identity,'company_id':user['company_id'],'role':'petugas','status':'aktif'}):
                raise HTTPException(409,'Ada petugas yang tidak aktif atau tidak ditemukan')
        account=await runtime.db.accounts.find_one({'id':assignment['account_id'],'company_id':user['company_id']})
        if not account or account.get('active_assignment_id')!=assignment_id:
            raise HTTPException(409,'Unit tidak lagi terikat pada penugasan ini')
        company=await runtime.db.companies.find_one({'id':user['company_id']}) or {}
        signature=company.get('director_signature')
        if not signature:raise HTTPException(409,'Unggah gambar stempel/tanda tangan perusahaan di Pengaturan sebelum approval')
        snapshot=copy.deepcopy(letter.get('document_snapshot') or await runtime.build_document_data(letter))
        snapshot.setdefault('company',{}).update(director_signature=signature,director_name=company.get('director_name',''),director_position=company.get('director_position','DIREKTUR'))
        snapshot.setdefault('letter',{})['status']='aktif'
        stamp={'approval_status':'APPROVED','approved_at':runtime.now_iso(),'approved_by':user['id'],'approved_by_name':user['name'],'updated_at':runtime.now_iso()}
        await runtime.db.assignment_letters.update_one({'id':letter['id'],'company_id':user['company_id']},{'$set':{**stamp,'status':'aktif','document_status':'ACTIVE','document_snapshot':snapshot,'snapshot_data':snapshot}})
        await runtime.db.assignments.update_one({'id':assignment_id,'company_id':user['company_id']},{'$set':{**stamp,'status':runtime.ASSIGNMENT_ACTIVE}})
        await runtime.log_audit(user,'Menyetujui surat tugas','assignment',assignment_id,request)
        return await runtime.enrich_letter({**letter,**stamp,'status':'aktif','document_status':'ACTIVE','document_snapshot':snapshot,'snapshot_data':snapshot})

    @router.get('/dashboard/finance')
    async def monthly_finance(user: dict = Depends(runtime.admin_required)):
        day=datetime.now(timezone(timedelta(hours=7))).date();first=day.replace(day=1)
        following=(first.replace(day=28)+timedelta(days=4)).replace(day=1)
        start,end=date_bounds(first.isoformat(),(following-timedelta(days=1)).isoformat())
        result=await runtime.db.finance_report(user['company_id'],start,end,'',1,1)
        from decimal import Decimal
        income=result['totals'].get('PEMASUKAN',Decimal('0'));expense=result['totals'].get('PENGELUARAN',Decimal('0'))
        return {'month':first.isoformat()[:7],'income':format(income,'.2f'),'expense':format(expense,'.2f'),'profit':format(income-expense,'.2f')}

    @router.get('/admin-users')
    async def administrators(page: int = Query(1,ge=1), user: dict = Depends(runtime.owner_required)):
        rows=await runtime.db.users.find({'company_id':user['company_id'],'role':'admin'},{'id':1,'name':1,'email':1,'status':1,'created_at':1}).sort([('created_at',-1),('id',1)]).skip((page-1)*50).to_list(51)
        return {'items':rows[:50],'next_page':page+1 if len(rows)>50 else None}

    @router.post('/admin-users')
    @runtime.transactional
    async def create_admin(data: AdminInput, request: Request, user: dict = Depends(runtime.owner_required)):
        email=str(data.email).strip().lower()
        if not data.name.strip() or len(data.password.encode())>72:raise HTTPException(400,'Nama wajib diisi dan password maksimal 72 byte')
        if await runtime.db.users.find_one({'email':email}):raise HTTPException(409,'Email sudah digunakan')
        record={'id':runtime.new_id(),'company_id':user['company_id'],'role':'admin','name':data.name.strip(),'email':email,'status':'aktif','token_version':0,'created_at':runtime.now_iso(),'created_by':user['id']}
        hashed=await runtime.run_in_threadpool(runtime.bcrypt.hashpw,data.password.encode(),runtime.bcrypt.gensalt())
        try:await runtime.db.users.insert_one({**record,'password_hash':hashed.decode()})
        except runtime.DuplicateKeyError:raise HTTPException(409,'Email sudah digunakan')
        await runtime.log_audit(user,'Membuat pengguna admin','user',record['id'],request)
        return record
