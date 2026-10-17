import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
import pytest
import bcrypt
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer
from test_workflow_audit import configure_assignment

OWNER={**ADMIN,'id':'owner','role':'owner','name':'Owner'}


def approval_setup(db,monkeypatch,actor=OWNER):
    db.users.find_one.side_effect=lambda q,*_: OFFICER if q.get('role')=='petugas' else actor
    letter={'id':'letter','company_id':'company-a','assignment_id':'assignment','status':'menunggu_approval','document_status':'PENDING_APPROVAL','approval_required':True,'approval_status':'PENDING','document_snapshot':{'company':{'name':'Company','director_signature':''},'letter':{}}}
    assignment={'id':'assignment','company_id':'company-a','status':'MENUNGGU_APPROVAL','approval_status':'PENDING','approval_required':True,'account_id':'unit','client_id':'leasing','power_of_attorney_id':'authority','officer_id':'officer','valid_until':'2099-12-31'}
    db.assignment_letters.find_one.return_value=letter;db.assignments.find_one.return_value=assignment
    db.power_of_attorneys.find_one.return_value={'status':'aktif','tanggal_berakhir':'2099-12-31'}
    db.clients.find_one.return_value={'status':'aktif'};db.accounts.find_one.return_value={'active_assignment_id':'assignment'}
    db.companies.find_one.return_value={'director_signature':'approved-stamp','director_name':'Director'}
    monkeypatch.setattr(server,'enrich_letter',AsyncMock(side_effect=lambda value:value))
    return letter,assignment


@pytest.mark.parametrize('actor',[ADMIN,OWNER])
def test_new_assignments_always_require_owner_even_created_by_owner(local_api,monkeypatch,actor):
    api,db=local_api
    server.app.dependency_overrides[server.admin_required]=lambda:actor
    configure_assignment(db,monkeypatch,{'status':'aktif','tanggal_berakhir':'2099-12-31'})
    response=api.post('/api/penugasan',json={'account_id':'unit','petugas_id':'officer'})
    assert response.status_code==200
    letter=response.json();assignment=db.assignments.insert_one.call_args.args[0]
    assert letter['status']=='menunggu_approval' and letter['document_status']=='PENDING_APPROVAL'
    assert letter['approval_required'] and assignment['status']=='MENUNGGU_APPROVAL'
    assert assignment['active_key']=='company-a:unit'


def test_owner_approval_captures_signature_and_activates_both_records(local_api,monkeypatch):
    api,db=local_api;approval_setup(db,monkeypatch)
    result=api.post('/api/penugasan/assignment/approve',headers=bearer(OWNER))
    assert result.status_code==200
    record=result.json()
    assert record['status']=='aktif' and record['approval_status']=='APPROVED'
    assert record['document_snapshot']['company']['director_signature']=='approved-stamp'
    assert db.assignments.update_one.call_args.args[1]['$set']['status']=='AKTIF'
    assert db.assignment_letters.update_one.call_args.args[1]['$set']['approved_by']=='owner'


@pytest.mark.parametrize('actor',[ADMIN,OFFICER])
def test_non_owner_cannot_approve_or_create_admin(local_api,monkeypatch,actor):
    api,db=local_api;approval_setup(db,monkeypatch,actor)
    for path in ('/penugasan/assignment/approve','/admin-users'):
        assert api.post('/api'+path,headers=bearer(actor),json={'name':'Admin','email':'a@example.com','password':'valid-test-password'}).status_code==403
    assert api.get('/api/approvals/pending-count',headers=bearer(actor)).status_code==403
    db.assignments.update_one.assert_not_called()


def test_pending_cannot_be_finalized_or_completed_by_admin(local_api,monkeypatch):
    api,db=local_api;approval_setup(db,monkeypatch,ADMIN)
    assert api.post('/api/surat-tugas/letter/finalize').status_code==403
    for state in ('aktif','selesai'):
        assert api.patch('/api/surat-tugas/letter/status',json={'status':state}).status_code==403
    assert api.get('/api/surat-tugas/letter/qr').status_code==403
    db.assignment_letters.update_one.assert_not_called()


def test_pending_payload_removes_all_nested_signatures(local_api):
    _,db=local_api
    db.companies.find_one.return_value={'nama':'Company','director_signature':'settings-stamp'}
    letter={'id':'letter','company_id':'company-a','approval_required':True,'approval_status':'PENDING','document_status':'PENDING_APPROVAL','status':'menunggu_approval','document_snapshot':{'company':{'director_signature':'bad-stamp'}}}
    payload=asyncio.run(server.get_document_payload(letter))
    assert payload['director_signature']=='' and not payload['is_finalized']
    assert 'director_signature' not in payload['data']['company']
    assert letter['document_snapshot']['company']['director_signature']=='bad-stamp'


def test_missing_stamp_or_expired_assignment_cannot_be_approved(local_api,monkeypatch):
    api,db=local_api;letter,assignment=approval_setup(db,monkeypatch)
    db.companies.find_one.return_value={}
    assert api.post('/api/penugasan/assignment/approve',headers=bearer(OWNER)).status_code==409
    assignment['valid_until']='2000-01-01'
    assert api.post('/api/penugasan/assignment/approve',headers=bearer(OWNER)).status_code==409
    db.assignments.update_one.assert_not_called()


def test_owner_create_admin_forces_role_and_hashes_password(local_api):
    api,db=local_api
    db.users.find_one.side_effect=lambda q,*_:None if 'email' in q else OWNER
    response=api.post('/api/admin-users',headers=bearer(OWNER),json={'name':'New Admin','email':'new@example.com','password':'valid-unit-password'})
    assert response.status_code==200 and response.json()['role']=='admin'
    assert 'password_hash' not in response.json()
    stored=db.users.insert_one.call_args.args[0]
    assert stored['company_id']==OWNER['company_id']
    assert bcrypt.checkpw(b'valid-unit-password',stored['password_hash'].encode())
    assert api.post('/api/admin-users',headers=bearer(OWNER),json={'name':'New Owner','email':'newowner@example.com','password':'valid-unit-password','role':'owner'}).status_code==422


def test_monthly_finance_uses_exact_totals_and_wib_bounds(local_api):
    api,db=local_api
    db.finance_report=AsyncMock(return_value={'totals':{'PEMASUKAN':Decimal('1500000.25'),'PENGELUARAN':Decimal('250000.10')}})
    response=api.get('/api/dashboard/finance')
    assert response.status_code==200
    assert response.json()['profit']=='1250000.15'
    args=db.finance_report.call_args.args
    assert args[0]=='company-a' and args[1].endswith('T17:00:00+00:00') and args[2].endswith('T17:00:00+00:00')


def test_bootstrap_owner_preserves_tenant_and_existing_password(local_api):
    from manage import bootstrap_owner
    _,db=local_api
    admin={**ADMIN,'email':'admin@example.com'}
    db.users.find_one.side_effect=[admin,None]
    async def commit(operation):return await operation()
    db.run_transaction=commit
    asyncio.run(bootstrap_owner(db,'Owner','owner@example.com','admin@example.com','owner-unit-test-password'))
    owner=db.users.insert_one.call_args.args[0]
    assert owner['role']=='owner' and owner['company_id']==ADMIN['company_id']
    assert bcrypt.checkpw(b'owner-unit-test-password',owner['password_hash'].encode())
    db.users.insert_one.reset_mock();db.users.find_one.side_effect=[admin,owner]
    asyncio.run(bootstrap_owner(db,'Owner','owner@example.com','admin@example.com','changed-password-unused'))
    db.users.insert_one.assert_not_called()
