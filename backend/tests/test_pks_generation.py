"""PKS generation: immutable identity, private PDFs, retry safety and signed archives."""
import io,uuid,copy
from datetime import date
from unittest.mock import Mock
import pytest
from pypdf import PdfReader,PdfWriter
from test_local_regressions import local_api,server,ADMIN,OFFICER,bearer
import pks,pks_document

COMPANY={'id':ADMIN['company_id'],'nama':'PT BERKAT INTIM GENERASI','alamat':'Jalan Perusahaan, Banjarbaru','telepon':'0812345678','email':'office@example.com','city':'Banjarbaru','director_name':'Direktur Contoh','director_position':'Direktur','director_signature':'PRIVATE-SIGNATURE','jwt_secret':'PRIVATE-SECRET'}
PERSON={**OFFICER,'name':'Mitra Contoh','nik':'1234567890123456','alamat':'Jalan Petugas, Banjarbaru','telepon':'0819876543','bank_name':'Bank Contoh','bank_branch':'Banjarbaru','bank_account_number':'00123456789','bank_account_name':'Mitra Contoh','petugas_code':'PTG-001','password_hash':'PRIVATE-HASH'}

def setup(db,monkeypatch):
    db.users.find_one.return_value=copy.deepcopy(PERSON)
    db.users.find_one_and_update.return_value=copy.deepcopy(PERSON)
    db.companies.find_one.return_value=copy.deepcopy(COMPANY)
    db.counters.find_one_and_update.return_value={'seq':7}
    monkeypatch.setattr(pks,'today',lambda:date(2026,11,12))
    monkeypatch.setattr(server,'put_object',Mock())

def payload(**kwargs):return {'officer_id':PERSON['id'],'duration':3,'unit':'TAHUN','submission_id':str(uuid.uuid4()),**kwargs}
def pdf():
    w=PdfWriter();w.add_blank_page(width=595,height=842);out=io.BytesIO();w.write(out);return out.getvalue()
def frozen():return pks_document.snapshot(COMPANY,PERSON,pks.period(3,'TAHUN',date(2026,11,12)),3,'TAHUN')

def test_template_contains_all_clauses_dynamic_parties_bank_and_period():
    content=pks_document.render(frozen(),'007/BIG-PKSM/XI/2026',False)
    pages=PdfReader(io.BytesIO(content)).pages;text='\n'.join(p.extract_text() for p in pages)
    assert len(pages)==2
    for word in ('Mitra Contoh','Direktur Contoh','00123456789','3 (tiga) tahun','12 November 2026','11 November 2029','007/BIG-PKSM/XI/2026','Halaman 1/2','Halaman 2/2'):
        assert word in text
    for n in range(1,13):assert f'PASAL {n}\n' in text
    for unwanted in ('PT SMS','PT Sejahtera','NURJANENA','PRIVATE-','DRAFT - BELUM'):assert unwanted not in text
    server.validate_pdf(content)

def test_long_identities_wrap_and_xml_is_literal():
    data=frozen();data['officer']['name']='<b>Mitra & Rekan</b>';data['officer']['alamat']='Alamat panjang '*80
    content=pks_document.render(data);text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(content)).pages)
    assert '<b>Mitra & Rekan</b>' in text and 'PASAL 12' in text and 'DRAFT - BELUM DITANDATANGANI' in text
    server.validate_pdf(content)

@pytest.mark.parametrize('role',['admin','owner'])
def test_generate_snapshots_profile_and_retry_returns_original(local_api,monkeypatch,role):
    api,db=local_api;setup(db,monkeypatch);server.app.dependency_overrides[server.admin_required]=lambda:{**ADMIN,'role':role}
    body=payload();response=api.post('/api/pks/generate',json=body);assert response.status_code==200,response.text
    out=response.json();assert out['status']=='DRAFT' and out['document_number']=='007/BIG-PKSM/XI/2026'
    assert 'document_snapshot' not in out
    record=db.documents.insert_one.call_args.args[0]
    assert record['document_snapshot']['officer']['bank_account_number']=='00123456789'
    assert record['document_snapshot']['start_date']=='2026-11-12' and record['document_snapshot']['end_date']=='2029-11-11'
    assert 'PRIVATE-' not in str(record)
    original=copy.deepcopy(record);db.documents.find_one.return_value=record
    db.users.find_one.return_value={**PERSON,'name':'Changed'};db.companies.find_one.return_value={**COMPANY,'director_name':'Changed'}
    server.put_object.reset_mock();db.counters.find_one_and_update.reset_mock()
    assert api.post('/api/pks/generate',json=body).json()['id']==out['id']
    assert record==original
    server.put_object.assert_not_called();db.counters.find_one_and_update.assert_not_called()
    assert api.post('/api/pks/generate',json={**body,'duration':2}).status_code==409

def test_preview_does_not_save_file_or_allocate_number(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch);body=payload();body.pop('submission_id')
    result=api.post('/api/pks/preview',json=body);assert result.status_code==200,result.text
    assert result.headers['content-type']=='application/pdf' and result.headers['cache-control']=='private, no-store'
    assert 'DRAFT/BIG-PKSM' in PdfReader(io.BytesIO(result.content)).pages[0].extract_text()
    db.documents.insert_one.assert_not_called();db.counters.find_one_and_update.assert_not_called();server.put_object.assert_not_called()

@pytest.mark.parametrize('changes',[{'duration':0},{'duration':1.5},{'duration':51},{'unit':'HARI'},{'start_date':'2000-01-01'},{'officer_id':''}])
def test_generation_rejects_invalid_or_client_owned_fields(local_api,monkeypatch,changes):
    api,db=local_api;setup(db,monkeypatch)
    assert api.post('/api/pks/generate',json=payload(**changes)).status_code in (400,422)
    server.put_object.assert_not_called()

@pytest.mark.parametrize('field',['alamat','bank_account_number','bank_account_name','nik'])
def test_missing_identity_is_actionable_without_storage(local_api,monkeypatch,field):
    api,db=local_api;setup(db,monkeypatch);db.users.find_one.return_value={**PERSON,field:''}
    response=api.post('/api/pks/generate',json=payload());assert response.status_code==400
    assert 'Petugas' in response.text or 'petugas' in response.text
    server.put_object.assert_not_called();db.upload_intents.insert_one.assert_not_called()

def test_foreign_officer_and_inactive_officer_rejected(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch);db.users.find_one.return_value=None
    assert api.post('/api/pks/generate',json=payload()).status_code==404
    assert db.users.find_one.call_args.args[0]['company_id']==ADMIN['company_id']
    db.users.find_one.return_value={**PERSON,'status':'nonaktif'}
    assert api.post('/api/pks/generate',json=payload()).status_code==400

@pytest.mark.parametrize('path',['/pks/generate','/pks/preview','/pks/id/signed'])
def test_officer_has_no_generation_or_archive_rights(local_api,path):
    api,db=local_api;server.app.dependency_overrides.pop(server.admin_required);db.users.find_one.return_value=OFFICER
    assert api.post('/api'+path,headers=bearer(OFFICER),json=payload()).status_code==403


def test_signed_archive_keeps_draft_identity_and_original_dates(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    record={'id':'pks','company_id':ADMIN['company_id'],'kind':'pks','source':'GENERATED','url':'/api/files/original.pdf','storage_path':'original.pdf','document_status':'DRAFT','start_date':'2026-11-12','end_date':'2029-11-11','document_snapshot':frozen()}
    db.documents.find_one.return_value=record;db.documents.find_one_and_update.return_value=record
    key=str(uuid.uuid4());files={'file':('signed.pdf',pdf(),'application/pdf')}
    result=api.post('/api/pks/pks/signed',data={'submission_id':key},files=files);assert result.status_code==200,result.text
    body=result.json();assert body['status']=='AKTIF' and body['url']==record['url'] and body['signed_url']!=body['url']
    assert body['start_date']==record['start_date'] and body['end_date']==record['end_date']
    assert db.documents.insert_one.call_args.args[0]['kind']=='pks_signed'
    update=db.documents.update_one.call_args.args[1]['$set'];assert 'document_snapshot' not in update and 'start_date' not in update
    db.documents.find_one.return_value={**record,**update};server.put_object.reset_mock()
    assert api.post('/api/pks/pks/signed',data={'submission_id':key},files=files).status_code==200
    server.put_object.assert_not_called()
    assert api.post('/api/pks/pks/signed',data={'submission_id':str(uuid.uuid4())},files=files).status_code==409


def test_signed_bad_pdf_and_other_tenant_do_not_store(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch);db.documents.find_one.return_value={'source':'GENERATED'}
    assert api.post('/api/pks/pks/signed',data={'submission_id':str(uuid.uuid4())},files={'file':('x.pdf',b'bad','application/pdf')}).status_code==400
    db.documents.find_one.return_value=None
    assert api.post('/api/pks/pks/signed',data={'submission_id':str(uuid.uuid4())},files={'file':('x.pdf',pdf(),'application/pdf')}).status_code==404
    server.put_object.assert_not_called()


def test_legacy_petugas_update_preserves_new_fields_when_omitted(local_api):
    api,db=local_api;db.users.find_one.side_effect=[None,PERSON]
    response=api.put('/api/petugas/'+PERSON['id'],json={'name':'Updated','email':'updated@example.com'})
    assert response.status_code==200,response.text
    update=db.users.update_one.call_args.args[1]['$set']
    assert not any(k in update for k in ('alamat','bank_name','bank_account_number','bank_account_name'))


def test_delete_pks_cleans_original_and_signed_attachment(local_api):
    api,db=local_api;prefix=server.APP_NAME+'/companies/'+ADMIN['company_id']+'/'
    db.documents.find_one.return_value={'id':'pks','storage_path':prefix+'draft.pdf'}
    db.documents.find.return_value.to_list.return_value=[{'id':'signed','storage_path':prefix+'signed.pdf'}]
    assert api.delete('/api/pks/pks').status_code==200
    assert db.documents.delete_many.call_args.args[0]=={'company_id':ADMIN['company_id'],'kind':'pks_signed','pks_id':'pks'}
    paths=[c.args[0]['id'] for c in db.upload_intents.update_one.call_args_list]
    assert set(paths)=={prefix+'draft.pdf',prefix+'signed.pdf'}
