"""Tenant-scoped Fonnte settings and transactional durable notification outbox."""
import asyncio
import base64
import hashlib
import os
import re
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

OWNER = "{perusahaan}: Penugasan {nomor_penugasan} dibuat oleh {admin}, menunggu approval owner. Silakan buka menu Penugasan."
PAYMENT = "{perusahaan}: Yth. {nama_petugas}, pembayaran tim untuk penugasan {nomor_penugasan} sebesar {nominal_tim} telah dicatat pada {tanggal_pembayaran}. Nominal ini adalah total tim ({jumlah_petugas} petugas). Silakan lihat laporan di aplikasi."
FIELDS = {'perusahaan', 'nomor_penugasan', 'admin', 'nama_petugas', 'nominal_tim', 'tanggal_pembayaran', 'jumlah_petugas'}


def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('fonnte:' + os.environ['JWT_SECRET']).encode()).digest()))


def phone(value):
    value = re.sub(r'[\s()+.-]', '', value or '')
    if value.startswith('00'): raise ValueError('Gunakan kode negara tanpa awalan 00')
    if value.startswith('0'): value = '62' + value[1:]
    if not re.fullmatch(r'[1-9]\d{8,14}', value):
        raise ValueError('Nomor WhatsApp harus valid, misalnya 081234567890 atau 6281234567890')
    return value


def template(value):
    try:
        for _, field, spec, conversion in string.Formatter().parse(value):
            if field is not None and (field not in FIELDS or spec or conversion): raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Placeholder pesan tidak dikenal atau format tidak valid')
    return value


class Settings(BaseModel):
    enabled: bool = False
    token: str = Field(default='', max_length=512)
    owner_phone: str = Field(default='', max_length=32)
    owner_template: str = Field(default=OWNER, min_length=1, max_length=4000)
    payment_template: str = Field(default=PAYMENT, min_length=1, max_length=4000)


def public(settings):
    return {k: settings.get(k, v) for k, v in {'enabled':False, 'owner_phone':'', 'owner_template':OWNER, 'payment_template':PAYMENT}.items()} | {'token_configured':bool(settings.get('token_encrypted'))}


async def enqueue(runtime, event, record, user):
    settings = await runtime.db.notification_settings.find_one({'id':user['company_id']}) or {}
    if not settings.get('enabled'): return
    company = await runtime.db.companies.find_one({'id':user['company_id']}) or {}
    assignment = record if event == 'approval' else await runtime.db.assignments.find_one({'id':record['assignment_id'], 'company_id':user['company_id']}) or {}
    values = dict.fromkeys(FIELDS, '')
    values.update(perusahaan=company.get('nama', 'Perusahaan'), nomor_penugasan=assignment.get('assignment_number', assignment.get('id', '-')), admin=user.get('name', ''), jumlah_petugas=str(len(set(record.get('petugas_ids') or [record.get('petugas_id')]))))
    if event == 'payment':
        values.update(nominal_tim='Rp ' + f"{Decimal(record['payment_amount']):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'), tanggal_pembayaran=datetime.fromisoformat(record['payment_recorded_at']).astimezone(timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M WIB'))
        recipients=[]
        for identity in dict.fromkeys(record.get('petugas_ids') or [record['petugas_id']]):
            person = await runtime.db.users.find_one({'id':identity, 'company_id':user['company_id'], 'role':'petugas'}) or {}
            recipients.append((identity, person.get('telepon', ''), person.get('name', identity)))
    else: recipients=[('owner', settings.get('owner_phone', ''), 'Owner')]
    for identity, number, name in recipients:
        job_id=hashlib.sha256(f"{user['company_id']}:{event}:{record['id']}:{identity}".encode()).hexdigest()
        if await runtime.db.whatsapp_notifications.find_one({'id':job_id}): continue
        try: number=phone(number); state='PENDING'; error=''
        except ValueError: state='FAILED'; error='Nomor WhatsApp penerima belum valid. Perbaiki nomor lalu coba ulang.'
        values['nama_petugas']=name
        message=template(settings.get('owner_template' if event == 'approval' else 'payment_template') or (OWNER if event == 'approval' else PAYMENT)).format_map(values)
        await runtime.db.whatsapp_notifications.insert_one({'id':job_id, 'company_id':user['company_id'], 'event':event, 'entity_id':record['id'], 'recipient_id':identity, 'recipient_name':name, 'target':number, 'message':message, 'status':state, 'error':error, 'created_at':runtime.now_iso(), 'updated_at':runtime.now_iso()})


def send(token, job):
    # Never retry an ambiguous network result: provider may already have accepted it.
    try:
        response=requests.post('https://api.fonnte.com/send', headers={'Authorization':token}, data={'target':job['target'], 'message':job['message'], 'countryCode':'62'}, timeout=(5, 20), allow_redirects=False)
        data=response.json()
        if response.ok and data.get('status') is True:
            return {'status':'ACCEPTED', 'provider_id':data.get('id', []), 'error':''}
        if response.ok and data.get('status') is False:
            return {'status':'FAILED', 'error':'Fonnte menolak pesan. Periksa token, koneksi perangkat dan kuota di Fonnte.'}
    except Exception:
        pass
    return {'status':'UNKNOWN', 'error':'Hasil pengiriman belum pasti. Periksa riwayat Fonnte sebelum mengirim ulang secara manual.'}


async def process_one(runtime):
    now=runtime.now_iso()
    # A process killed after claiming may have sent the message; never blindly resend.
    stale=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
    await runtime.db.whatsapp_notifications.update_many({'status':'SENDING', 'updated_at':{'$lt':stale}}, {'$set':{'status':'UNKNOWN', 'error':'Proses pengiriman terputus. Periksa riwayat Fonnte.', 'updated_at':now}})
    enabled=await runtime.db.notification_settings.find({'enabled':True}).to_list(None)
    if not enabled: return
    jobs=await runtime.db.whatsapp_notifications.find({'status':'PENDING', 'company_id':{'$in':[item['id'] for item in enabled]}}).sort('created_at', 1).to_list(20)
    for job in jobs:
        settings=await runtime.db.notification_settings.find_one({'id':job['company_id']}) or {}
        if not settings.get('enabled'): continue
        if job['event']=='approval':
            assignment=await runtime.db.assignments.find_one({'id':job['entity_id'], 'company_id':job['company_id']})
            if not assignment or assignment.get('status')!='MENUNGGU_APPROVAL':
                await runtime.db.whatsapp_notifications.update_one({'id':job['id'], 'status':'PENDING'}, {'$set':{'status':'SKIPPED', 'error':'Penugasan tidak lagi menunggu approval.', 'updated_at':now}})
                continue
        try: token=cipher().decrypt(settings.get('token_encrypted', '').encode()).decode()
        except (InvalidToken, ValueError):
            await runtime.db.whatsapp_notifications.update_one({'id':job['id'], 'status':'PENDING'}, {'$set':{'status':'FAILED', 'error':'Token tidak dapat dibaca. Simpan ulang token Fonnte.', 'updated_at':now}})
            continue
        async def claim():
            return await runtime.db.whatsapp_notifications.find_one_and_update({'id':job['id'], 'status':'PENDING'}, {'$set':{'status':'SENDING', 'updated_at':runtime.now_iso()}}, return_document=True)
        claimed=await runtime.transactions.run(runtime.client, claim)
        if not claimed: continue
        result=await asyncio.to_thread(send, token, claimed)
        await runtime.db.whatsapp_notifications.update_one({'id':job['id'], 'status':'SENDING'}, {'$set':{**result, 'updated_at':runtime.now_iso()}})


async def worker(runtime):
    while True:
        try:
            if runtime.app.state.database_ready: await process_one(runtime)
        except Exception as exc:
            runtime.logger.warning('WhatsApp worker: %s', type(exc).__name__)
        await asyncio.sleep(5)


def register(router, runtime):
    @router.get('/whatsapp/settings')
    async def get_settings(user:dict=Depends(runtime.admin_required)):
        return public(await runtime.db.notification_settings.find_one({'id':user['company_id']}) or {})

    @router.put('/whatsapp/settings')
    @runtime.transactional
    async def save_settings(data:Settings, request:Request, user:dict=Depends(runtime.admin_required)):
        old=await runtime.db.notification_settings.find_one({'id':user['company_id']}) or {}
        values=data.model_dump(exclude={'token'})
        values['owner_template']=template(data.owner_template)
        values['payment_template']=template(data.payment_template)
        if data.owner_phone:
            try: values['owner_phone']=phone(data.owner_phone)
            except ValueError as exc: raise HTTPException(422, str(exc))
        if data.token.strip():
            if any(c in data.token for c in '\r\n'): raise HTTPException(422, 'Token tidak valid')
            values['token_encrypted']=cipher().encrypt(data.token.strip().encode()).decode()
        elif old.get('token_encrypted'): values['token_encrypted']=old['token_encrypted']
        if data.enabled and (not values.get('token_encrypted') or not values['owner_phone']):
            raise HTTPException(422, 'Token Fonnte dan nomor WhatsApp owner wajib diisi sebelum mengaktifkan')
        values.update(id=user['company_id'], company_id=user['company_id'], updated_at=runtime.now_iso())
        if old: await runtime.db.notification_settings.update_one({'id':user['company_id']}, {'$set':values})
        else: await runtime.db.notification_settings.insert_one(values)
        await runtime.log_audit(user, 'Mengubah pengaturan WhatsApp Fonnte', 'notification_settings', user['company_id'], request)
        return public(values)

    @router.get('/whatsapp/notifications')
    async def history(user:dict=Depends(runtime.admin_required)):
        return await runtime.db.whatsapp_notifications.find({'company_id':user['company_id']}, {'_id':0}).sort('created_at', -1).to_list(50)

    @router.post('/whatsapp/notifications/{identity}/retry')
    @runtime.transactional
    async def retry(identity:str, request:Request, user:dict=Depends(runtime.admin_required)):
        scope={'id':identity, 'company_id':user['company_id']}
        job=await runtime.db.whatsapp_notifications.find_one(scope)
        if not job: raise HTTPException(404, 'Notifikasi tidak ditemukan')
        if job['status']!='FAILED': raise HTTPException(409, 'Hanya pesan yang gagal pasti dapat dicoba ulang; pesan diterima/ambigu tidak dikirim ulang untuk mencegah duplikasi')
        settings=await runtime.db.notification_settings.find_one({'id':user['company_id']}) or {}
        if not settings.get('enabled'): raise HTTPException(409, 'Aktifkan Fonnte terlebih dahulu')
        if job['recipient_id']=='owner': number=settings.get('owner_phone', '')
        else:
            person=await runtime.db.users.find_one({'id':job['recipient_id'], 'company_id':user['company_id'], 'role':'petugas'}) or {}
            number=person.get('telepon', '')
        try: number=phone(number)
        except ValueError as exc: raise HTTPException(422, str(exc))
        await runtime.db.whatsapp_notifications.update_one({**scope, 'status':'FAILED'}, {'$set':{'status':'PENDING', 'target':number, 'error':'', 'updated_at':runtime.now_iso()}})
        await runtime.log_audit(user, 'Mencoba ulang notifikasi WhatsApp', 'whatsapp_notifications', identity, request)
        return {'status':'PENDING'}
