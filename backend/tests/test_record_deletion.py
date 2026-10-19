import asyncio
from unittest.mock import AsyncMock
import pytest
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer

PATHS=['penugasan','surat-tugas','laporan','leasing-payments','pks']

@pytest.mark.parametrize('path',PATHS+['admin-users'])
def test_officers_cannot_delete_operational_or_finance_records(local_api,path):
    api,db=local_api
    server.app.dependency_overrides.pop(server.admin_required)
    db.users.find_one.return_value=OFFICER
    assert api.delete('/api/'+path+'/record',headers=bearer(OFFICER)).status_code==403

@pytest.mark.parametrize('path',PATHS)
def test_missing_or_foreign_record_is_not_deleted(local_api,path):
    api,db=local_api
    assert api.delete('/api/'+path+'/foreign').status_code==404
    for collection in [db.assignments,db.field_reports,db.documents,db.assignment_letters]:
        collection.delete_one.assert_not_called()


def test_assignment_with_report_gives_actionable_error_and_preserves_data(local_api):
    api,db=local_api
    db.assignments.find_one.return_value={'id':'task','account_id':'unit'}
    db.field_reports.find_one.return_value={'id':'report'}
    response=api.delete('/api/penugasan/task')
    assert response.status_code==409 and 'Laporan Lapangan' in response.text
    db.assignments.delete_one.assert_not_called();db.assignment_letters.delete_one.assert_not_called()


def test_assignment_deletion_cleans_letters_chat_and_notices_and_releases_only_its_unit(local_api):
    api,db=local_api
    db.assignments.find_one.side_effect=[{'id':'task','account_id':'unit'},None]
    db.assignment_letters.find.return_value.to_list.return_value=[{'id':'letter','document_number':'018/BIG-SKS/X/2026'}]
    response=api.request('DELETE','/api/penugasan/task',json={'reason':'Penugasan salah pilih unit'})
    assert response.status_code==200
    assert db.assignment_letters.delete_one.call_args.args[0]=={'id':'letter','company_id':ADMIN['company_id']}
    assert db.chat_messages.delete_many.call_args.args[0]['assignment_id']=='task'
    first=db.accounts.update_many.call_args_list[0].args[0]
    assert first['active_assignment_id']=='task' and first['id']=='unit'
    audit=db.audit_logs.insert_one.call_args.args[0]
    assert audit['deletion_reason']=='Penugasan salah pilih unit'
    assert audit['deleted_data']['document_number']=='018/BIG-SKS/X/2026'
    assert db.whatsapp_notifications.update_many.call_args.args[1]['$set']['status']=='SKIPPED'


def test_report_deletion_scopes_files_and_restores_only_matching_active_assignment(local_api):
    api,db=local_api
    db.field_reports.find_one.return_value={'id':'report','assignment_id':'task','account_id':'unit','status':'TIDAK_DITEMUKAN','payment_amount':'500000.00','payment_status':'SELESAI','account_snapshot':{'status':'DITUGASKAN'}}
    db.accounts.find_one.return_value={'id':'unit','active_assignment_id':'task','status':server.ACCOUNT_STATUS_MAP['TIDAK_DITEMUKAN']}
    assert api.delete('/api/laporan/report').status_code==200
    scope=db.report_photos.delete_many.call_args.args[0]
    assert scope=={'report_id':'report','company_id':ADMIN['company_id']}
    assert db.accounts.update_one.call_args.args[0]['active_assignment_id']=='task'
    assert db.accounts.update_one.call_args.args[1]['$set']['status']=='DITUGASKAN'
    assert db.audit_logs.insert_one.call_args.args[0]['deleted_data']['payment_amount']=='500000.00'
    assert db.field_reports.delete_one.call_args.args[0]['company_id']==ADMIN['company_id']


def test_report_deletion_does_not_change_a_newer_assignment(local_api):
    api,db=local_api
    db.field_reports.find_one.return_value={'id':'report','assignment_id':'old','account_id':'unit','status':'TIDAK_DITEMUKAN'}
    db.accounts.find_one.return_value={'id':'unit','active_assignment_id':'new','status':server.ACCOUNT_STATUS_MAP['TIDAK_DITEMUKAN']}
    assert api.delete('/api/laporan/report').status_code==200
    db.accounts.update_one.assert_not_called()

@pytest.mark.parametrize('path,kind',[('leasing-payments','leasing_payment'),('pks','pks')])
def test_document_deletion_checks_kind_scopes_company_and_retains_audit(local_api,path,kind):
    api,db=local_api
    db.documents.find_one.return_value={'id':'record','payment_amount':'100.00','password_hash':'SECRET'}
    assert api.delete('/api/'+path+'/record').status_code==200
    assert db.documents.delete_one.call_args.args[0]=={'id':'record','company_id':ADMIN['company_id'],'kind':kind}
    assert 'SECRET' not in str(db.audit_logs.insert_one.call_args)


def test_uploaded_sk_can_be_deleted_when_it_has_no_business_dependencies(local_api):
    api,db=local_api
    db.power_of_attorneys.find_one.return_value={'id':'sk'}
    db.documents.find_one.return_value={'id':'own-pdf','kind':'surat_kuasa','ref_id':'sk'}
    assert api.delete('/api/surat-kuasa/sk').status_code==200
    assert db.documents.delete_many.call_args.args[0]=={'company_id':ADMIN['company_id'],'kind':'surat_kuasa','ref_id':'sk'}


def test_idempotency_cache_cannot_return_a_deleted_creation(local_api):
    api,db=local_api
    db.idempotency.find_one.return_value={'deleted':True}
    result=api.post('/api/clients',json={'nama_perusahaan':'Leasing'},headers={'Idempotency-Key':'deleted-example-request'})
    assert result.status_code==409 and 'sudah dihapus' in result.text
    db.clients.insert_one.assert_not_called()
