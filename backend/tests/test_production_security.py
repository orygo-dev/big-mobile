import asyncio, io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from test_local_regressions import local_api, ADMIN, bearer, server
from pdf_validation import validate_pdf
from pypdf import PdfWriter
import storage


def test_cookie_login_is_httponly_and_does_not_return_production_token(local_api, monkeypatch):
    api, db = local_api
    monkeypatch.setattr(server.security, "PRODUCTION", True)
    db.users.find_one.return_value = {**ADMIN, "email":"admin@example.com", "password_hash":"hash"}
    monkeypatch.setattr(server,"verify_password",lambda *_:True)
    response=api.post('/api/auth/login',json={'email':'admin@example.com','password':'valid-password'})
    assert response.status_code==200
    assert 'token' not in response.json()
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie


def test_access_token_cannot_authenticate_through_file_url(local_api):
    api, db=local_api
    token=server.create_access_token(ADMIN['id'],'admin')
    assert api.get('/api/files/photo.jpg?auth='+token).status_code==401
    server.get_object.assert_not_called()


def test_revoked_token_cannot_access_api_or_photo(local_api):
    api, db=local_api
    db.users.find_one.return_value=ADMIN
    db.revoked_tokens.find_one.return_value={'id':'revoked'}
    for path in ['/api/auth/me','/api/files/photo.jpg']:
        assert api.get(path,headers=bearer()).status_code==401


def test_password_version_invalidates_existing_sessions(local_api):
    api, db=local_api
    db.users.find_one.return_value={**ADMIN,'token_version':1}
    assert api.get('/api/auth/me',headers=bearer()).status_code==401


def test_cross_origin_mutation_is_rejected(local_api):
    api, db=local_api
    assert api.post('/api/clients',json={'nama_perusahaan':'Blocked'},headers={'Origin':'https://attacker.example'}).status_code==403
    db.clients.insert_one.assert_not_called()


def test_ip_limit_uses_atomic_counter(local_api):
    api, db=local_api
    db.rate_limits.find_one_and_update.return_value={'count':31}
    assert api.post('/api/auth/login',json={'email':'someone@example.com','password':'invalid'}).status_code==429
    db.users.find_one.assert_not_called()


def test_json_mutation_idempotency_does_not_repeat_business_write(local_api):
    api, db=local_api
    db.idempotency.find_one.return_value={'fingerprint':__import__('hashlib').sha256(__import__('json').dumps(server.ClientInput(nama_perusahaan='Finance').model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest(),'response':{'id':'already-created'}}
    response=api.post('/api/clients',json={'nama_perusahaan':'Finance'},headers={'Idempotency-Key':'request-key-1234'})
    assert response.status_code==200 and response.json()['id']=='already-created'
    db.clients.insert_one.assert_not_called()


def test_idempotency_key_cannot_be_reused_for_changed_data(local_api):
    api, db=local_api
    db.idempotency.find_one.return_value={'fingerprint':'different','response':{}}
    assert api.post('/api/clients',json={'nama_perusahaan':'Changed'},headers={'Idempotency-Key':'request-key-1234'}).status_code==409
    db.clients.insert_one.assert_not_called()


def test_pdf_validation_rejects_active_content_and_corruption():
    for content in [b'%PDF bad data',None]:
        if content is None:
            writer=PdfWriter(); writer.add_blank_page(width=100,height=100);writer.add_js('app.alert(1)')
            stream=io.BytesIO();writer.write(stream);content=stream.getvalue()
        with pytest.raises(Exception):validate_pdf(content)
    writer=PdfWriter();writer.add_blank_page(width=100,height=100)
    stream=io.BytesIO();writer.write(stream);validate_pdf(stream.getvalue())


def test_s3_private_upload_uses_encryption(monkeypatch):
    client=Mock()
    monkeypatch.setattr(storage,'STORAGE_BACKEND','s3');monkeypatch.setattr(storage,'_s3',client)
    monkeypatch.setenv('S3_BUCKET','private-test')
    storage.put_object('fieldcollector/companies/test/proof.jpg',b'proof','image/jpeg')
    assert client.put_object.call_args.kwargs['ServerSideEncryption']=='AES256'
    assert 'ACL' not in client.put_object.call_args.kwargs


def test_cleanup_does_not_delete_referenced_upload(local_api, monkeypatch):
    _, db=local_api
    item={'id':'path','company_id':'company-a','storage_path':'fieldcollector/companies/company-a/reports/proof.jpg'}
    db.upload_intents.find.return_value.to_list.return_value=[item]
    db.report_photos.find_one.return_value={'report_id':'valid'}
    deleter=Mock();monkeypatch.setattr(server,'delete_object',deleter)
    asyncio.run(server.reconcile_uploads())
    deleter.assert_not_called();db.upload_intents.delete_one.assert_awaited_once()


def test_mysql_nested_operations_reuse_transaction_connection():
    from database import Database, connection_context
    database=Database('mysql://qa:qa@localhost/test')
    connection=object();token=connection_context.set(connection)
    async def check():
        async with database.connection() as active:
            assert active is connection
        called=AsyncMock(return_value='result')
        assert await database.run_transaction(called)=='result'
        called.assert_awaited_once()
    try:asyncio.run(check())
    finally:connection_context.reset(token)


def test_nonexistent_client_deactivation_is_not_reported_as_success(local_api):
    api,db=local_api
    from types import SimpleNamespace
    db.clients.update_one.return_value=SimpleNamespace(matched_count=0)
    assert api.patch('/api/clients/missing/deactivate').status_code==404
    db.audit_logs.insert_one.assert_not_called()


def test_logo_upload_requires_a_real_png(local_api):
    api,db=local_api
    response=api.post('/api/company/logo',files={'file':('bad.png',b'\x89PNGnot-a-real-image','image/png')})
    assert response.status_code==400
    db.companies.update_one.assert_not_called()


def test_required_master_fields_reject_blank_input(local_api):
    api,db=local_api
    assert api.post('/api/clients',json={'nama_perusahaan':'   '}).status_code==422
    db.clients.insert_one.assert_not_called()


@pytest.mark.parametrize('variable,value',[
    ('MYSQL_URL','mysql://application@127.0.0.1/big_mobile'),
    ('MYSQL_URL','mysql://application:password@mysql.internal/big_mobile'),
    ('MYSQL_URL','mysql://root:password@127.0.0.1/big_mobile'),
    ('MYSQL_URL','mysql://application:password@127.0.0.1/big_mobile?ssl_verify=false'),
    ('APP_BASE_URL','http://app.example.com'),
    ('DB_TRANSACTIONS','false'),
    ('SEED_DEMO_DATA','true'),
])
def test_production_rejects_unsafe_configuration(monkeypatch,variable,value):
    import secrets
    monkeypatch.setattr(server.security,'PRODUCTION',True)
    for key,item in {'JWT_SECRET':secrets.token_urlsafe(48),'APP_BASE_URL':'https://app.example.com','CORS_ORIGINS':'https://app.example.com','MYSQL_URL':'mysql://application:password@127.0.0.1/big_mobile','DB_TRANSACTIONS':'true','SEED_DEMO_DATA':'false','FILE_STORAGE_BACKEND':'local','MONITOR_TOKEN':secrets.token_urlsafe(32)}.items():monkeypatch.setenv(key,item)
    server.security.validate_configuration()
    monkeypatch.setenv(variable,value)
    with pytest.raises(RuntimeError):server.security.validate_configuration()
