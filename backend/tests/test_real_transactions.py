"""Opt-in integration tests against an isolated DB on a real replica set."""
import os, sys, uuid, secrets, subprocess, socket, time, io
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import bcrypt, jwt, requests, pytest
from pymongo import MongoClient
from PIL import Image

pytestmark=pytest.mark.skipif(not os.environ.get('MONGO_TEST_URI'),reason='Set MONGO_TEST_URI to a test replica set; never uses a public demo')


@pytest.fixture(scope='module')
def live(tmp_path_factory):
    root=Path(__file__).resolve().parents[2]
    temporary=tmp_path_factory.mktemp('real-transactions')
    mongo=MongoClient(os.environ['MONGO_TEST_URI'],serverSelectionTimeoutMS=5000)
    assert mongo.admin.command('hello').get('setName'),'Integration target must support transactions'
    name='audit_production_'+uuid.uuid4().hex
    db=mongo[name]
    company='company-'+uuid.uuid4().hex
    password=secrets.token_urlsafe(24)
    users={}
    for label,role in [('admin','admin'),('officer','petugas'),('other','petugas'),('foreign','admin')]:
        person={'id':uuid.uuid4().hex,'company_id':company if label!='foreign' else 'foreign-company','role':role,'name':'QA '+label,'email':label+'.'+name+'@example.com','status':'aktif','petugas_code':label,'password_hash':bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()}
        db.users.insert_one(person);users[label]=person
    db.companies.insert_one({'id':company,'nama':'Production QA','company_code':'QA','app_name':'BIG Mobile'})
    secret=secrets.token_urlsafe(48)
    env={**os.environ,'APP_ENV':'production','MONGO_URL':os.environ['MONGO_TEST_URI'],'DB_NAME':name,'JWT_SECRET':secret,'DB_TRANSACTIONS':'true','FILE_STORAGE_BACKEND':'local','LOCAL_STORAGE_DIR':str(temporary/'uploads'),'APP_BASE_URL':'https://qa.example.com','CORS_ORIGINS':'https://qa.example.com','SEED_DEMO_DATA':'false','MONITOR_TOKEN':secrets.token_urlsafe(32)}
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));web_port=sock.getsockname()[1]
    env['CORS_ORIGINS']+=f',https://localhost:{web_port}'
    env['ALLOW_INSECURE_LOCAL_TEST_DATABASE']='true'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    output=(temporary/'server.log').open('w')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=root/'backend',env=env,stdout=output,stderr=output)
    url=f'http://127.0.0.1:{port}/api'
    tokens={label:jwt.encode({'sub':user['id'],'role':user['role'],'type':'access','ver':0,'iss':'big-mobile-api','aud':'big-mobile','jti':uuid.uuid4().hex,'iat':datetime.now(timezone.utc),'exp':datetime.now(timezone.utc)+timedelta(hours=1)},secret,algorithm='HS256') for label,user in users.items()}
    def call(who,method,path,expected=200,**kwargs):
        headers={**kwargs.pop('headers',{}),'Authorization':'Bearer '+tokens[who]}
        response=requests.request(method,url+path,headers=headers,timeout=30,**kwargs)
        assert response.status_code==expected,f'{method} {path}: {response.status_code} {response.text[:200]}'
        return response
    try:
        for _ in range(60):
            if process.poll() is not None:raise RuntimeError('Integration server failed; inspect isolated server.log')
            try:
                if requests.get(url+'/health',timeout=2).status_code==200:break
            except requests.RequestException:pass
            time.sleep(1)
        else:raise RuntimeError('Integration readiness timed out')
        yield {'db':db,'users':users,'call':call,'url':url,'tokens':tokens,'env':env,'temporary':temporary,'root':root,'password':password,'web_port':web_port}
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        output.close()
        assert name.startswith('audit_production_')
        mongo.drop_database(name);mongo.close()


def unit(live):
    call=live['call'];suffix=uuid.uuid4().hex
    client=call('admin','POST','/clients',json={'nama_perusahaan':'QA '+suffix}).json()
    sk=call('admin','POST','/surat-kuasa',json={'nomor':suffix,'client_id':client['id'],'tanggal_berlaku':'2020-01-01','tanggal_berakhir':'2099-12-31'}).json()
    account=call('admin','POST','/akun',json={'nomor_kontrak':suffix,'nama_debitur':'QA Debitur','client_id':client['id'],'surat_kuasa_id':sk['id']}).json()
    return account,sk


def assign(live,account):
    return live['call']('admin','POST','/penugasan',json={'account_id':account['id'],'petugas_id':live['users']['officer']['id']}).json()


def report_payload(letter,account):
    return {'assignment_id':letter['assignment_id'],'account_id':account['id'],'status':'TIDAK_DITEMUKAN','catatan':'Kunjungan sudah dilaksanakan dengan lengkap','latitude':'-6.2','longitude':'106.8'}


def test_assignment_failure_rolls_back_letter_unit_counter_and_audit(live):
    account,_=unit(live);db=live['db']
    audits=db.audit_logs.count_documents({})
    counters=list(db.counters.find({}))
    db.command('collMod','assignment_letters',validator={'id':{'$exists':False}},validationLevel='strict')
    try:
        live['call']('admin','POST','/penugasan',500,json={'account_id':account['id'],'petugas_id':live['users']['officer']['id']})
        assert db.assignments.count_documents({'account_id':account['id']})==0
        assert db.accounts.find_one({'id':account['id']})['status']=='BELUM_DITUGASKAN'
        assert db.audit_logs.count_documents({})==audits
        assert list(db.counters.find({}))==counters
    finally:db.command('collMod','assignment_letters',validator={})


def test_concurrent_assignment_only_one_commits(live):
    account,_=unit(live)
    body={'account_id':account['id'],'petugas_id':live['users']['officer']['id']}
    def send():return requests.post(live['url']+'/penugasan',json=body,headers={'Authorization':'Bearer '+live['tokens']['admin']},timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:send(),range(2)))
    assert sorted(response.status_code for response in responses)==[200,400]
    assert live['db'].assignments.count_documents({'account_id':account['id'],'status':'AKTIF'})==1


def test_idempotent_assignment_returns_original_result(live):
    account,_=unit(live)
    body={'account_id':account['id'],'petugas_id':live['users']['officer']['id']}
    headers={'Idempotency-Key':uuid.uuid4().hex}
    first=live['call']('admin','POST','/penugasan',json=body,headers=headers).json()
    second=live['call']('admin','POST','/penugasan',json=body,headers=headers).json()
    assert first['assignment_id']==second['assignment_id']
    assert live['db'].assignments.count_documents({'account_id':account['id']})==1


def test_real_photo_report_review_isolation_and_renewal(live):
    account,sk=unit(live);letter=assign(live,account)
    image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG')
    payload=report_payload(letter,account);payload['status']='UNIT_DITEMUKAN'
    report=live['call']('officer','POST','/laporan',data=payload,files={'photos':('proof.png',image.getvalue(),'image/png')}).json()
    path=report['photos'][0]['url'][4:]
    assert live['call']('admin','GET',path).content==image.getvalue()
    live['call']('other','GET',path,404);live['call']('foreign','GET',path,404)
    live['call']('foreign','GET','/laporan/'+report['id'],404)
    live['call']('admin','PATCH','/laporan/'+report['id']+'/review',json={'catatan_admin':'Bukti sudah direview'})
    history=live['call']('officer','GET','/my/riwayat').json()
    assert next(item for item in history if item['id']==report['id'])['catatan_admin']=='Bukti sudah direview'
    live['call']('admin','PATCH','/surat-tugas/'+letter['id']+'/status',json={'status':'selesai'})
    new_sk=live['call']('admin','POST','/surat-kuasa',json={'nomor':uuid.uuid4().hex,'client_id':account['client_id']}).json()
    updated={key:value for key,value in account.items() if key in {'nomor_kontrak','nama_debitur','client_id','surat_kuasa_id'}}
    updated.update({'surat_kuasa_id':new_sk['id'],'nama_debitur':'Updated current master'})
    live['call']('admin','PUT','/akun/'+account['id'],json=updated)
    assert live['call']('admin','GET','/laporan/'+report['id']).json()['account']['nama_debitur']=='QA Debitur'
    assert live['db'].upload_intents.count_documents({'company_id':account['company_id']})==0


def test_report_metadata_failure_rolls_back_and_orphan_file_is_cleaned(live):
    account,_=unit(live);letter=assign(live,account);db=live['db']
    image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG')
    db.command('collMod','report_photos',validator={'id':{'$exists':False}},validationLevel='strict')
    try:
        payload=report_payload(letter,account);payload['status']='UNIT_DITEMUKAN'
        live['call']('officer','POST','/laporan',500,data=payload,files={'photos':('proof.png',image.getvalue(),'image/png')})
        assert db.field_reports.count_documents({'assignment_id':letter['assignment_id']})==0
        assert db.accounts.find_one({'id':account['id']})['status']=='DITUGASKAN'
        intents=list(db.upload_intents.find({}))
        assert intents
        db.upload_intents.update_many({}, {'$set':{'created_at':datetime.now(timezone.utc)-timedelta(hours=2)}})
        code='import asyncio, server; asyncio.run(server.reconcile_uploads()); server.client.close()'
        subprocess.run([sys.executable,'-c',code],cwd=live['root']/'backend',env=live['env'],check=True,capture_output=True,timeout=30)
        assert db.upload_intents.count_documents({})==0
        assert not (Path(live['env']['LOCAL_STORAGE_DIR'])/intents[0]['storage_path']).exists()
    finally:db.command('collMod','report_photos',validator={})


def test_concurrent_reports_and_cancellation_remain_consistent(live):
    account,_=unit(live);letter=assign(live,account);payload=report_payload(letter,account)
    def send():return requests.post(live['url']+'/laporan',data=payload,headers={'Authorization':'Bearer '+live['tokens']['officer']},timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:send(),range(2)))
    assert sorted(response.status_code for response in responses)==[200,400]
    assert live['db'].field_reports.count_documents({'assignment_id':letter['assignment_id']})==1
    account2,_=unit(live);letter2=assign(live,account2)
    def cancellation():return live['call']('admin','PATCH','/surat-tugas/'+letter2['id']+'/status',json={'status':'dibatalkan'})
    def reporting():return requests.post(live['url']+'/laporan',data=report_payload(letter2,account2),headers={'Authorization':'Bearer '+live['tokens']['officer']},timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:
        close=pool.submit(cancellation);report=pool.submit(reporting);close.result();outcome=report.result()
    assert outcome.status_code in {200,400,409}
    assert live['db'].assignments.find_one({'id':letter2['assignment_id']})['status']=='DIBATALKAN'
    assert live['db'].assignments.count_documents({'account_id':account2['id'],'active_key':{'$exists':True}})==0


def test_logout_revokes_access_and_production_login_sets_secure_cookie(live):
    response=requests.post(live['url']+'/auth/login',json={'email':live['users']['other']['email'],'password':live['password']},timeout=30)
    assert response.status_code==200 and 'token' not in response.json()
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    live['call']('other','POST','/auth/logout')
    live['call']('other','GET','/auth/me',401)
    # Later ownership tests need an independently authenticated session.
    payload=jwt.decode(live['tokens']['other'],live['env']['JWT_SECRET'],algorithms=['HS256'],audience='big-mobile',issuer='big-mobile-api')
    payload['jti']=uuid.uuid4().hex
    live['tokens']['other']=jwt.encode(payload,live['env']['JWT_SECRET'],algorithm='HS256')


def test_paginated_master_data_and_historical_report_search(live):
    company=live['users']['admin']['company_id']
    live['db'].clients.insert_many([{'id':uuid.uuid4().hex,'company_id':company,'nama_perusahaan':'Pagination QA','status':'aktif','created_at':'2099-01-01'} for _ in range(3)])
    first=live['call']('admin','GET','/clients?search=Pagination%20QA&limit=2')
    second=live['call']('admin','GET','/clients?search=Pagination%20QA&limit=2&page=2')
    assert len(first.json())==2 and len(second.json())==1
    assert first.headers['X-Total-Count']=='3' and first.headers['X-Next-Page']=='2'
    assert len({item['id'] for item in first.json()+second.json()})==3
    reports=live['call']('admin','GET','/laporan?search=QA%20Debitur&limit=1')
    assert len(reports.json())==1
    assert reports.json()[0]['nama_debitur']=='QA Debitur'


def test_real_pdf_access_and_company_upload_audit_rollback(live):
    from pypdf import PdfWriter
    account,sk=unit(live)
    stream=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(stream)
    uploaded=live['call']('admin','POST','/surat-kuasa/'+sk['id']+'/file',files={'file':('authority.pdf',stream.getvalue(),'application/pdf')}).json()
    path=uploaded['file_url'][4:]
    assert live['call']('admin','GET',path).content==stream.getvalue()
    live['call']('officer','GET',path,404)
    assign(live,account)
    assert live['call']('officer','GET','/my/tugas/'+account['id']).json()['surat_kuasa_file']==uploaded['file_url']
    assert live['call']('officer','GET',path).content==stream.getvalue()
    live['call']('foreign','GET',path,404)
    image=io.BytesIO();Image.new('RGBA',(32,32),(0,120,255,128)).save(image,format='PNG')
    db=live['db'];before=db.companies.find_one({'id':live['users']['admin']['company_id']}).get('logo')
    db.command('collMod','audit_logs',validator={'id':{'$exists':False}},validationLevel='strict')
    try:
        live['call']('admin','POST','/company/logo',500,files={'file':('logo.png',image.getvalue(),'image/png')})
        assert db.companies.find_one({'id':live['users']['admin']['company_id']}).get('logo')==before
    finally:db.command('collMod','audit_logs',validator={})
    uploaded=live['call']('admin','POST','/company/logo',files={'file':('logo.png',image.getvalue(),'image/png')}).json()
    assert uploaded['logo'].startswith('data:image/png;base64,')


@pytest.mark.skipif(os.environ.get('RUN_BROWSER_TESTS')!='true',reason='Set RUN_BROWSER_TESTS=true after building frontend and installing Playwright browser')
def test_https_browser_workflow_and_network_recovery(live):
    import json, ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.now(timezone.utc)
    certificate=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
    temporary=live['temporary'];key_path=temporary/'qa.key';cert_path=temporary/'qa.crt';image=temporary/'photo.png'
    from pypdf import PdfWriter
    pdf=temporary/'authority.pdf';writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    with pdf.open('wb') as output:writer.write(output)
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM));Image.new('RGB',(64,64),'blue').save(image)
    fixture=temporary/'browser-fixture.json'
    print_pdf=temporary/'printed-letter.pdf'
    fixture.write_text(json.dumps({'api_url':live['url'],'web_port':live['web_port'],'key':str(key_path),'cert':str(cert_path),'image':str(image),'pdf':str(pdf),'print_pdf':str(print_pdf),'password':live['password'],'admin_email':live['users']['admin']['email'],'officer_email':live['users']['officer']['email'],'admin_token':live['tokens']['admin']}))
    try:
        result=subprocess.run(['node',str(live['root']/'frontend/e2e/workflow.mjs')],env={**os.environ,'E2E_FIXTURE_PATH':str(fixture)},capture_output=True,text=True,timeout=240)
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        from pypdf import PdfReader
        reader=PdfReader(print_pdf)
        assert 1 <= len(reader.pages) <= 3
        assert 'Browser Debitur' in ''.join(page.extract_text() for page in reader.pages)
    finally:fixture.unlink(missing_ok=True)

def test_chat_attachment_location_idempotency_and_historical_access(live):
    import json
    from pypdf import PdfWriter
    account,_=unit(live);letter=assign(live,account);task=letter['assignment_id'];call=live['call'];db=live['db']
    photo=io.BytesIO();Image.new('RGB',(32,32),'orange').save(photo,'PNG')
    pdf=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(pdf)
    data={'client_message_id':str(uuid.uuid4()),'text':'Koordinasi kunjungan','location':json.dumps({'latitude':-6.2,'longitude':106.8,'accuracy':10})}
    files=[('files',('photo.png',photo.getvalue(),'image/png')),('files',('document.pdf',pdf.getvalue(),'application/pdf'))]
    message=call('officer','POST',f'/chat/{task}/messages',data=data,files=files).json()
    assert message['sequence']==1 and len(message['attachments'])==2 and 'fingerprint' not in message
    assert all('storage_path' not in item for item in message['attachments'])
    assert call('officer','POST',f'/chat/{task}/messages',data=data,files=files).json()['id']==message['id']
    call('officer','POST',f'/chat/{task}/messages',409,data={**data,'text':'Changed'},files=files)
    assert db.chat_messages.count_documents({'assignment_id':task})==1
    for attachment in message['attachments']:
        path=attachment['url'].removeprefix('/api')
        response=call('admin','GET',path)
        assert response.headers['x-content-type-options']=='nosniff'
        assert response.headers['content-disposition'].startswith('inline' if attachment['kind']=='image' else 'attachment')
        call('foreign','GET',path,404);call('other','GET',path,404)
    assert call('admin','GET',f'/chat/{task}').json()['unread']==1
    assert call('admin','GET','/chat/unread').json()['count']>=1
    call('admin','POST',f'/chat/{task}/read',json={'sequence':9999})
    assert call('admin','GET',f'/chat/{task}').json()['unread']==0
    call('admin','POST',f'/chat/{task}/read',json={'sequence':0})
    assert call('admin','GET',f'/chat/{task}').json()['unread']==0
    call('other','GET',f'/chat/{task}',404);call('foreign','GET',f'/chat/{task}',404)
    inbox=call('officer','GET','/chat').json()['items'];assert any(item['assignment_id']==task for item in inbox)
    call('admin','PATCH',f"/surat-tugas/{letter['id']}/status",json={'status':'selesai'})
    assert call('officer','GET',f'/chat/{task}').json()['assignment']['read_only']
    assert call('officer','POST',f'/chat/{task}/messages',data=data,files=files).json()['id']==message['id']
    call('officer','POST',f'/chat/{task}/messages',409,data={'client_message_id':str(uuid.uuid4()),'text':'Closed'})
    call('officer','GET',message['attachments'][0]['url'].removeprefix('/api'))


def test_chat_concurrent_retry_sequence_and_pagination(live):
    account,_=unit(live);letter=assign(live,account);task=letter['assignment_id'];call=live['call'];db=live['db']
    data={'client_message_id':str(uuid.uuid4()),'text':'Retry in parallel'}
    def send():return requests.post(live['url']+f'/chat/{task}/messages',headers={'Authorization':'Bearer '+live['tokens']['officer']},data=data,timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:send(),range(2)))
    assert [r.status_code for r in responses]==[200,200]
    assert responses[0].json()['id']==responses[1].json()['id']
    assert db.chat_messages.count_documents({'assignment_id':task})==1
    for index in range(4):call('admin','POST',f'/chat/{task}/messages',data={'client_message_id':str(uuid.uuid4()),'text':f'Message {index}'})
    latest=call('officer','GET',f'/chat/{task}?limit=2').json();assert [m['sequence'] for m in latest['messages']]==[4,5] and latest['has_more']
    previous=call('officer','GET',f'/chat/{task}?before=4&limit=2').json();assert [m['sequence'] for m in previous['messages']]==[2,3]
    following=call('officer','GET',f'/chat/{task}?after=1&limit=2').json();assert [m['sequence'] for m in following['messages']]==[2,3] and following['has_more']


def test_chat_audit_failure_rolls_back_message_and_sequence(live):
    account,_=unit(live);letter=assign(live,account);task=letter['assignment_id'];db=live['db'];call=live['call']
    db.command('collMod','audit_logs',validator={'id':{'$exists':False}},validationLevel='strict')
    try:
        call('admin','POST',f'/chat/{task}/messages',500,data={'client_message_id':str(uuid.uuid4()),'text':'Must roll back'})
        assert db.chat_messages.count_documents({'assignment_id':task})==0
        assert not db.assignments.find_one({'id':task}).get('chat_sequence')
    finally:db.command('collMod','audit_logs',validator={})


def test_chat_invalid_file_and_owner_have_no_upload(live):
    account,_=unit(live);letter=assign(live,account);task=letter['assignment_id'];call=live['call'];db=live['db']
    before=db.upload_intents.count_documents({})
    call('other','POST',f'/chat/{task}/messages',404,data={'client_message_id':str(uuid.uuid4()),'text':'Blocked'})
    call('officer','POST',f'/chat/{task}/messages',400,data={'client_message_id':str(uuid.uuid4())},files={'files':('fake.pdf',b'invalid','application/pdf')})
    call('officer','POST',f'/chat/{task}/messages',400,data={'client_message_id':str(uuid.uuid4())},files={'files':('app.exe',b'fake','application/octet-stream')})
    assert db.upload_intents.count_documents({})==before
    assert db.chat_messages.count_documents({'assignment_id':task})==0

def test_chat_send_racing_close_never_writes_after_closed_state(live):
    account,_=unit(live);letter=assign(live,account);task=letter['assignment_id'];db=live['db']
    def send():return requests.post(live['url']+f'/chat/{task}/messages',headers={'Authorization':'Bearer '+live['tokens']['officer']},data={'client_message_id':str(uuid.uuid4()),'text':'Race with closing'},timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:
        closing=pool.submit(live['call'],'admin','PATCH',f"/surat-tugas/{letter['id']}/status",json={'status':'selesai'})
        pending=pool.submit(send);closing.result();response=pending.result()
    assert response.status_code in {200,409}
    assert db.assignments.find_one({'id':task})['status']=='SELESAI'
    assert db.chat_messages.count_documents({'assignment_id':task})==int(response.status_code==200)
    live['call']('officer','POST',f'/chat/{task}/messages',409,data={'client_message_id':str(uuid.uuid4()),'text':'Definitely closed'})
