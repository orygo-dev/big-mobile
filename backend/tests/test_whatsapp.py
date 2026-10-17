import asyncio
from unittest.mock import Mock, AsyncMock
import pytest
from fastapi import HTTPException
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer, configure_admin_report, admin_report_data, admin_report_photos, login_background_png
import whatsapp


def configured(db):
    settings={'id':ADMIN['company_id'],'enabled':True,'owner_phone':'6281234567890','token_encrypted':whatsapp.cipher().encrypt(b'test-token').decode()}
    db.notification_settings.find_one.return_value=settings
    db.notification_settings.find.return_value.to_list.return_value=[settings]
    return settings


@pytest.mark.parametrize('value,expected',[('0812 3456 7890','6281234567890'),('+62 812-3456-7890','6281234567890')])
def test_phone_normalization(value,expected):
    assert whatsapp.phone(value)==expected


@pytest.mark.parametrize('value',['abc','123','0812<script>','+0000000000'])
def test_invalid_phone(value):
    with pytest.raises(ValueError):whatsapp.phone(value)


@pytest.mark.parametrize('value',['{token}','{perusahaan.__class__}','{perusahaan!r}','{perusahaan:>999999}','{'])
def test_template_rejects_unknown_or_unsafe_fields(value):
    with pytest.raises(HTTPException):whatsapp.template(value)


def test_settings_encrypt_token_and_never_return_it(local_api):
    api,db=local_api
    result=api.put('/api/whatsapp/settings',json={'enabled':True,'token':'test-token','owner_phone':'081234567890'})
    assert result.status_code==200
    assert result.json()['token_configured'] and 'test-token' not in result.text
    saved=db.notification_settings.insert_one.call_args.args[0]
    assert 'token' not in saved and whatsapp.cipher().decrypt(saved['token_encrypted'].encode())==b'test-token'
    db.notification_settings.find_one.return_value=saved
    result=api.put('/api/whatsapp/settings',json={'enabled':True,'token':'','owner_phone':'081234567890'})
    assert result.status_code==200
    assert db.notification_settings.update_one.call_args.args[1]['$set']['token_encrypted']==saved['token_encrypted']
    assert 'test-token' not in api.get('/api/whatsapp/settings').text
    assert 'test-token' not in str(db.audit_logs.insert_one.call_args)


def test_activation_requires_credentials(local_api):
    api,db=local_api
    assert api.put('/api/whatsapp/settings',json={'enabled':True}).status_code==422
    db.notification_settings.insert_one.assert_not_called()


def test_officer_cannot_access_settings_or_history(local_api):
    api,db=local_api
    server.app.dependency_overrides.pop(server.admin_required)
    db.users.find_one.return_value=OFFICER
    for path in ['/whatsapp/settings','/whatsapp/notifications']:
        assert api.get('/api'+path,headers=bearer(OFFICER)).status_code==403


def test_payment_creates_one_notice_per_team_member_with_team_total(local_api):
    _,db=local_api;configured(db)
    db.companies.find_one.return_value={'nama':'PT BIG'}
    db.assignments.find_one.return_value={'assignment_number':'TASK-1'}
    db.users.find_one.side_effect=[{'name':'A','telepon':'081234567890'},{'name':'B','telepon':''}]
    record={'id':'report','assignment_id':'assignment','petugas_ids':['a','b','a'],'payment_amount':'500000.00','payment_recorded_at':'2026-10-18T00:00:00+00:00'}
    asyncio.run(whatsapp.enqueue(server,'payment',record,ADMIN))
    rows=[call.args[0] for call in db.whatsapp_notifications.insert_one.call_args_list]
    assert len(rows)==2 and rows[0]['status']=='PENDING' and rows[1]['status']=='FAILED'
    assert 'Rp 500.000,00' in rows[0]['message'] and 'total tim' in rows[0]['message'] and '2 petugas' in rows[0]['message']
    assert 'WIB' in rows[0]['message']
    assert db.users.find_one.call_args_list[0].args[0]['company_id']==ADMIN['company_id']


def test_disabled_does_not_enqueue(local_api):
    _,db=local_api
    asyncio.run(whatsapp.enqueue(server,'approval',{'id':'assignment'},ADMIN))
    db.whatsapp_notifications.insert_one.assert_not_called()


def test_existing_event_not_enqueued_twice(local_api):
    _,db=local_api;configured(db)
    db.whatsapp_notifications.find_one.return_value={'id':'existing'}
    asyncio.run(whatsapp.enqueue(server,'approval',{'id':'assignment'},ADMIN))
    db.whatsapp_notifications.insert_one.assert_not_called()


@pytest.mark.parametrize('response,state', [({'status':True,'id':['provider-1']},'ACCEPTED'),({'status':False,'detail':'bad token'},'FAILED')])
def test_provider_contract(monkeypatch,response,state):
    transport=Mock(return_value=Mock(ok=True,json=Mock(return_value=response)))
    monkeypatch.setattr(whatsapp.requests,'post',transport)
    assert whatsapp.send('secret',{'target':'6281234567890','message':'notice'})['status']==state
    assert transport.call_args.kwargs['headers']=={'Authorization':'secret'}
    assert transport.call_args.args[0]=='https://api.fonnte.com/send'


def test_timeout_is_ambiguous_and_never_automatically_retried(monkeypatch):
    transport=Mock(side_effect=TimeoutError)
    monkeypatch.setattr(whatsapp.requests,'post',transport)
    assert whatsapp.send('secret',{'target':'6281234567890','message':'notice'})['status']=='UNKNOWN'
    assert transport.call_count==1


def test_worker_only_sends_claimed_jobs(local_api,monkeypatch):
    _,db=local_api;configured(db)
    job={'id':'job','company_id':ADMIN['company_id'],'event':'payment','target':'6281234567890','message':'hello'}
    db.whatsapp_notifications.find.return_value.to_list.return_value=[job]
    db.whatsapp_notifications.find_one_and_update.return_value=None
    transport=Mock(return_value={'status':'ACCEPTED','error':''})
    monkeypatch.setattr(whatsapp,'send',transport)
    asyncio.run(whatsapp.process_one(server));transport.assert_not_called()
    db.whatsapp_notifications.find_one_and_update.return_value=job
    asyncio.run(whatsapp.process_one(server));assert transport.call_count==1
    assert db.whatsapp_notifications.update_one.call_args.args[1]['$set']['status']=='ACCEPTED'


def test_retry_cannot_resend_accepted_or_ambiguous_jobs(local_api):
    api,db=local_api
    for status in ['ACCEPTED','UNKNOWN','SENDING','PENDING']:
        db.whatsapp_notifications.find_one.return_value={'status':status}
        assert api.post('/api/whatsapp/notifications/id/retry').status_code==409
    db.whatsapp_notifications.update_one.assert_not_called()


def test_failed_retry_refreshes_phone_and_scopes_company(local_api):
    api,db=local_api;configured(db)
    db.whatsapp_notifications.find_one.return_value={'status':'FAILED','recipient_id':'officer'}
    db.users.find_one.return_value={'telepon':'081234567890'}
    assert api.post('/api/whatsapp/notifications/id/retry').status_code==200
    scope,update=db.whatsapp_notifications.update_one.call_args.args
    assert scope['company_id']==ADMIN['company_id'] and update['$set']['target']=='6281234567890'


def test_paid_creation_enqueues_but_unpaid_creation_does_not(local_api,monkeypatch):
    api,db=local_api;configure_admin_report(db,monkeypatch)
    hook=AsyncMock();monkeypatch.setattr(whatsapp,'enqueue',hook)
    assert api.post('/api/laporan',data=admin_report_data(),files=admin_report_photos()).status_code==200
    hook.assert_not_called()
    files=list(admin_report_photos().items())+[('payment_proof',('payment.png',login_background_png(),'image/png'))]
    assert api.post('/api/laporan',data=admin_report_data(),files=files).status_code==200
    assert hook.call_count==1 and hook.call_args.args[1]=='payment'
