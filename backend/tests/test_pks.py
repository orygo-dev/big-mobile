import uuid
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from pypdf import PdfWriter
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer
import pks


def pdf():
    writer=PdfWriter();writer.add_blank_page(width=595,height=842);output=BytesIO();writer.write(output);return output.getvalue()


def setup(db,monkeypatch):
    db.users.find_one.return_value=OFFICER;db.users.find_one_and_update.return_value=OFFICER
    monkeypatch.setattr(server,'put_object',Mock())
    monkeypatch.setattr(pks,'today',lambda:date(2026,10,17))


def data(**extra):
    return {'officer_id':OFFICER['id'],'duration':'3','unit':'TAHUN','submission_id':str(uuid.uuid4()),**extra}


def file():return {'file':('PKS.pdf',pdf(),'application/pdf')}


@pytest.mark.parametrize('start,duration,unit,end',[
    (date(2026,10,17),3,'TAHUN','2029-10-16'),
    (date(2026,10,17),6,'BULAN','2027-04-16'),
    (date(2026,12,31),2,'BULAN','2027-02-27'),
    (date(2024,2,29),1,'TAHUN','2025-02-27'),
])
def test_calendar_duration(start,duration,unit,end):
    assert pks.period(duration,unit,start)=={'start_date':start.isoformat(),'end_date':end}


@pytest.mark.parametrize('days,expected',[(31,'AKTIF'),(30,'MENDEKATI_EXPIRED'),(1,'MENDEKATI_EXPIRED'),(0,'MENDEKATI_EXPIRED'),(-1,'EXPIRED')])
def test_status_boundary_days(days,expected):
    current=date(2026,10,17)
    assert pks.status({'start_date':'2026-01-01','end_date':(current+timedelta(days=days)).isoformat()},current)==expected


def test_future_status():
    assert pks.status({'start_date':'2026-11-01','end_date':'2027-10-31'},date(2026,10,17))=='BELUM_AKTIF'


def test_create_dates_are_server_owned_and_retry_is_idempotent(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    payload=data(start_date='2000-01-01',end_date='2099-12-31')
    response=api.post('/api/pks',data=payload,files=file())
    assert response.status_code==200
    record=response.json()
    assert record['start_date']=='2026-10-17' and record['end_date']=='2029-10-16'
    assert record['officer_name']==OFFICER['name'] and record['status']=='AKTIF'
    assert record['url'].startswith('/api/files/') and 'storage_path' not in record
    stored=db.documents.insert_one.call_args.args[0]
    assert stored['company_id']==ADMIN['company_id'] and stored['kind']=='pks'
    db.documents.find_one.return_value=stored;server.put_object.reset_mock();db.documents.insert_one.reset_mock()
    replay=api.post('/api/pks',data=payload,files=file())
    assert replay.status_code==200 and replay.json()['id']==record['id']
    server.put_object.assert_not_called();db.documents.insert_one.assert_not_called()
    assert api.post('/api/pks',data={**payload,'duration':'2'},files=file()).status_code==409


@pytest.mark.parametrize('duration,unit',[('0','TAHUN'),('-1','BULAN'),('1.5','TAHUN'),('51','TAHUN'),('601','BULAN'),('3','HARI')])
def test_invalid_duration_rejected_before_storage(local_api,monkeypatch,duration,unit):
    api,db=local_api;setup(db,monkeypatch)
    assert api.post('/api/pks',data=data(duration=duration,unit=unit),files=file()).status_code in (400,422)
    server.put_object.assert_not_called()


def test_pdf_required_and_foreign_officer_rejected(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    assert api.post('/api/pks',data=data()).status_code==422
    assert api.post('/api/pks',data=data(),files={'file':('bad.pdf',b'bad','application/pdf')}).status_code==400
    assert api.post('/api/pks',data=data(),files={'file':('image.png',b'bad','image/png')}).status_code==400
    db.users.find_one.return_value=None
    assert api.post('/api/pks',data=data(),files=file()).status_code==404
    assert db.users.find_one.call_args.args[0]=={'id':OFFICER['id'],'company_id':ADMIN['company_id'],'role':'petugas'}
    server.put_object.assert_not_called()


def test_preview_uses_server_today(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    assert api.get('/api/pks/period?duration=3&unit=TAHUN').json()=={'start_date':'2026-10-17','end_date':'2029-10-16','timezone':'Asia/Jakarta'}


def test_listing_scoped_and_status_filter_uses_boundaries(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    cursor=db.documents.find.return_value;cursor.limit.return_value=cursor
    cursor.to_list.return_value=[{'id':'one','start_date':'2026-01-01','end_date':'2026-11-16','kind':'pks','storage_path':'secret'}]
    response=api.get('/api/pks?state=MENDEKATI_EXPIRED')
    assert response.status_code==200 and response.json()['items'][0]['status']=='MENDEKATI_EXPIRED'
    assert 'storage_path' not in response.json()['items'][0]
    query=db.documents.find.call_args.args[0]
    assert query['company_id']==ADMIN['company_id'] and query['kind']=='pks'
    assert query['end_date']=={'$gte':'2026-10-17','$lte':'2026-11-16'}


def test_officer_search_labels_and_safe_fields(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    cursor=db.users.find.return_value;cursor.limit.return_value=cursor;cursor.to_list.return_value=[OFFICER]
    response=api.get('/api/pks/officers?search=Officer')
    assert response.status_code==200 and response.json()['items'][0]['pks_status']=='BELUM_MEMILIKI'
    query,projection=db.users.find.call_args.args
    assert query['company_id']==ADMIN['company_id'] and query['role']=='petugas'
    assert set(projection)=={'id','name','petugas_code','status'}
    db.documents.find.return_value.to_list.return_value=[{'start_date':'2026-01-01','end_date':'2026-10-16'}]
    assert api.get('/api/pks/officers').json()['items'][0]['pks_status']=='EXPIRED'


def test_officer_cannot_list_create_or_open_pks(local_api,monkeypatch):
    api,db=local_api;setup(db,monkeypatch)
    server.app.dependency_overrides.pop(server.admin_required)
    for path in ('/pks','/pks/officers','/pks/period?duration=3'):
        assert api.get('/api'+path,headers=bearer(OFFICER)).status_code==403
    assert api.post('/api/pks',headers=bearer(OFFICER),data=data(),files=file()).status_code==403
    db.documents.find_one.return_value={'kind':'pks','company_id':OFFICER['company_id']}
    assert api.get('/api/files/pks.pdf',headers=bearer(OFFICER)).status_code==404
    server.get_object.assert_not_called()


def test_officer_with_pks_cannot_be_deleted(local_api):
    api,db=local_api;db.users.find_one.return_value=OFFICER;db.documents.find_one.return_value={'kind':'pks'}
    assert api.delete('/api/petugas/'+OFFICER['id']).status_code==409
    db.users.delete_one.assert_not_called()
