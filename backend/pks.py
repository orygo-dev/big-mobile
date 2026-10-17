"""Private officer cooperation agreements with server-owned validity dates."""
import calendar
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from admin_reports import fingerprint, request_id

KIND = 'pks'
WIB = timezone(timedelta(hours=7))


def today():
    return datetime.now(WIB).date()


def period(duration, unit, start=None):
    months = duration * (12 if unit == 'TAHUN' else 1)
    if unit not in ('BULAN', 'TAHUN') or duration < 1 or months > 600:
        raise HTTPException(400, 'Durasi harus bilangan bulat positif, maksimal 50 tahun atau 600 bulan.')
    first = start or today()
    year, month = divmod(first.year*12+first.month-1+months, 12)
    anniversary = date(year, month+1, min(first.day, calendar.monthrange(year, month+1)[1]))
    return {'start_date': first.isoformat(), 'end_date': (anniversary-timedelta(days=1)).isoformat()}


def status(record, current=None):
    current = current or today()
    first, last = date.fromisoformat(record['start_date']), date.fromisoformat(record['end_date'])
    if current < first:return 'BELUM_AKTIF'
    days = (last-current).days
    if days < 0:return 'EXPIRED'
    return 'MENDEKATI_EXPIRED' if days <= 30 else 'AKTIF'


def public(record, current=None):
    return {**{key:value for key,value in record.items() if key not in {'_id','storage_path','fingerprint','company_id','kind'}}, 'status':status(record,current)}


def register(router, runtime):
    @router.get('/pks/period')
    async def preview(duration: int = Query(..., ge=1, le=600), unit: Literal['BULAN','TAHUN'] = 'TAHUN', user: dict = Depends(runtime.admin_required)):
        return {**period(duration,unit), 'timezone':'Asia/Jakarta'}

    @router.get('/pks/officers')
    async def officers(search: str = Query('', max_length=120), page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=50), user: dict = Depends(runtime.admin_required)):
        current = today();query = {'company_id':user['company_id'], 'role':'petugas'}
        if search.strip():
            pattern = {'$regex':re.escape(search.strip()), '$options':'i'}
            query['$or'] = [{'name':pattern}, {'petugas_code':pattern}]
        rows = await runtime.db.users.find(query, {'id':1,'name':1,'petugas_code':1,'status':1}).sort([('name',1),('id',1)]).skip((page-1)*limit).limit(limit+1).to_list(limit+1)
        items = []
        for officer in rows[:limit]:
            scope = {'company_id':user['company_id'], 'kind':KIND, 'officer_id':officer['id']}
            # Prefer a currently valid agreement over a future/expired history entry.
            existing = await runtime.db.documents.find({**scope,'start_date':{'$lte':current.isoformat()},'end_date':{'$gte':current.isoformat()}}, {'_id':0}).sort([('end_date',-1),('created_at',-1)]).to_list(1)
            if not existing:
                existing = await runtime.db.documents.find(scope, {'_id':0}).sort([('end_date',-1),('created_at',-1)]).to_list(1)
            record = existing[0] if existing else None
            items.append({**officer, 'pks_status':status(record,current) if record else 'BELUM_MEMILIKI', 'pks_end_date':record['end_date'] if record else None})
        return {'items':items, 'next_page':page+1 if len(rows)>limit else None}

    @router.get('/pks')
    async def listing(search: str = Query('', max_length=120), state: Literal['','AKTIF','MENDEKATI_EXPIRED','EXPIRED','BELUM_AKTIF'] = '', page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), user: dict = Depends(runtime.admin_required)):
        current = today();day = current.isoformat();near = (current+timedelta(days=30)).isoformat()
        query = {'company_id':user['company_id'],'kind':KIND}
        if search.strip():query['officer_name'] = {'$regex':re.escape(search.strip()),'$options':'i'}
        if state == 'EXPIRED':query['end_date'] = {'$lt':day}
        elif state == 'BELUM_AKTIF':query['start_date'] = {'$gt':day}
        elif state:
            query['start_date'] = {'$lte':day}
            query['end_date'] = {'$gt':near} if state=='AKTIF' else {'$gte':day,'$lte':near}
        rows = await runtime.db.documents.find(query, {'_id':0}).sort([('created_at',-1),('id',-1)]).skip((page-1)*limit).limit(limit+1).to_list(limit+1)
        return {'items':[public(row,current) for row in rows[:limit]], 'next_page':page+1 if len(rows)>limit else None, 'today':day}

    @router.post('/pks')
    async def create(request: Request, officer_id: str = Form(...), duration: int = Form(..., ge=1, le=600), unit: Literal['BULAN','TAHUN'] = Form(...), submission_id: str = Form(...), file: UploadFile = File(...), user: dict = Depends(runtime.admin_required)):
        dates = period(duration,unit)
        key = request_id(submission_id)
        if file.content_type != 'application/pdf':raise HTTPException(400,'File PKS harus berupa PDF, maksimal 8 MB.')
        content = await file.read(runtime.MAX_FILE_SIZE+1)
        if not content or len(content)>runtime.MAX_FILE_SIZE:raise HTTPException(400,'File PKS wajib diisi dan maksimal 8 MB.')
        try:
            await run_in_threadpool(runtime.validate_pdf,content)
        except Exception:
            raise HTTPException(400,'PDF PKS tidak valid, terkunci, atau mengandung konten aktif.')
        prepared = {'content':content,'kind':KIND,'name':(file.filename or 'PKS.pdf').replace('\\','/').split('/')[-1][:160]}
        digest = fingerprint([officer_id,duration,unit],[prepared])
        identity = str(uuid.uuid5(uuid.NAMESPACE_URL,f"pks:{user['company_id']}:{key}"))
        scope = {'id':identity,'company_id':user['company_id'],'kind':KIND}
        def cached(record):
            if record.get('fingerprint')!=digest:raise HTTPException(409,'ID pengiriman sudah dipakai untuk PKS berbeda. Muat ulang formulir.')
            return public(record)
        existing = await runtime.db.documents.find_one(scope)
        if existing:return cached(existing)
        owner = {'id':officer_id,'company_id':user['company_id'],'role':'petugas'}
        if not await runtime.db.users.find_one(owner):raise HTTPException(404,'Petugas tidak ditemukan.')
        path = f"{runtime.APP_NAME}/companies/{user['company_id']}/pks/{identity}/{runtime.new_id()}.pdf"
        await runtime.db.upload_intents.insert_one({'id':path,'company_id':user['company_id'],'storage_path':path,'created_at':datetime.now(timezone.utc)})
        await run_in_threadpool(runtime.put_object,path,content,'application/pdf')
        async def commit():
            officer = await runtime.db.users.find_one_and_update(owner,{'$inc':{'relation_version':1}},return_document=True)
            if not officer:raise HTTPException(404,'Petugas tidak ditemukan.')
            existing = await runtime.db.documents.find_one(scope)
            if existing:return cached(existing)
            record = {**scope,**dates,'officer_id':officer_id,'officer_name':officer['name'],'officer_code':officer.get('petugas_code',''),'duration':duration,'duration_unit':unit,'created_at':runtime.now_iso(),'created_by':user['id'],'filename':prepared['name'],'url':'/api/files/'+path,'storage_path':path,'fingerprint':digest}
            await runtime.db.documents.insert_one(dict(record))
            await runtime.db.upload_intents.delete_one({'id':path,'company_id':user['company_id']})
            await runtime.log_audit(user,'Membuat PKS petugas',KIND,identity,request)
            return public(record)
        return await runtime.transactions.run(runtime.client,commit)
