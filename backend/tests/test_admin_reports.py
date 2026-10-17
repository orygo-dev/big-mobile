import uuid
from unittest.mock import Mock
import pytest
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer, configure_admin_report, admin_report_data, admin_report_photos, login_background_png
from admin_reports import amount, fingerprint
from fastapi import HTTPException


@pytest.mark.parametrize('value', ['0', '-1', 'NaN', 'Infinity', '1.234', '1000000000000', '', 'abc'])
def test_invalid_payment_amount_is_rejected(value):
    with pytest.raises(HTTPException): amount(value)


def test_payment_amount_uses_exact_decimal_storage():
    assert amount('1234567890.12') == '1234567890.12'
    assert amount('500000') == '500000.00'


def test_create_pending_report_multiple_images(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    files = [('photos', ('first.png', login_background_png(), 'image/png')), ('photos', ('second.png', login_background_png(), 'image/png'))]
    response = api.post('/api/laporan', data=admin_report_data(), files=files)
    assert response.status_code == 200
    report = response.json()
    assert report['payment_status'] == 'MENUNGGU_PEMBAYARAN'
    assert report['report_status'] == 'MENUNGGU_PEMBAYARAN'
    assert report['payment_amount'] == '500000.00' and report['payment_scope'] == 'TEAM'
    assert report['created_by'] == ADMIN['id'] and report['petugas_ids'] == [OFFICER['id']]
    assert len(report['photos']) == 2 and not report.get('payment_proof')


def test_create_paid_report_does_not_mix_proof_with_field_images(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    files = [('photos', ('field.png', login_background_png(), 'image/png')), ('payment_proof', ('payment.png', login_background_png(), 'image/png'))]
    response = api.post('/api/laporan', data=admin_report_data(), files=files)
    assert response.status_code == 200
    report = response.json()
    assert report['payment_status'] == 'SELESAI' and report['payment_proof']['kind'] == 'payment'
    assert len(report['photos']) == 1
    assert [call.args[0]['kind'] for call in db.report_photos.insert_one.call_args_list] == ['report','payment']


def test_report_requires_field_evidence_even_if_payment_is_uploaded(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    response = api.post('/api/laporan', data=admin_report_data(), files={'payment_proof': ('payment.png', login_background_png(), 'image/png')})
    assert response.status_code == 400
    server.put_object.assert_not_called()


def test_invalid_payment_proof_prevents_all_uploads(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    response = api.post('/api/laporan', data=admin_report_data(), files=[('photos', ('field.png', login_background_png(), 'image/png')), ('payment_proof', ('bad.pdf', b'bad', 'application/pdf'))])
    assert response.status_code == 400
    server.put_object.assert_not_called()


def test_create_retry_returns_existing_report_without_new_upload(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    data = admin_report_data()
    first = api.post('/api/laporan', data=data, files=admin_report_photos()).json()
    db.field_reports.find_one.return_value = first
    server.put_object.reset_mock(); db.field_reports.insert_one.reset_mock()
    second = api.post('/api/laporan', data=data, files=admin_report_photos())
    assert second.status_code == 200 and second.json()['id'] == first['id']
    server.put_object.assert_not_called(); db.field_reports.insert_one.assert_not_called()


def test_late_payment_finishes_same_report(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    pending = {'id':'report', 'company_id':'company-a', 'payment_amount':'500000.00', 'payment_status':'MENUNGGU_PEMBAYARAN'}
    db.field_reports.find_one.return_value = pending
    db.field_reports.find_one_and_update.return_value = pending
    response = api.post('/api/laporan/report/payment', data={'payment_request_id': str(uuid.uuid4())}, files={'file': ('payment.png', login_background_png(), 'image/png')})
    assert response.status_code == 200
    assert response.json()['id'] == 'report' and response.json()['payment_status'] == 'SELESAI'
    assert response.json()['payment_amount'] == '500000.00'
    db.field_reports.insert_one.assert_not_called()


def test_paid_report_cannot_be_overwritten(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    db.field_reports.find_one.return_value = {'id':'report', 'payment_amount':'500000.00', 'payment_proof':{'url':'original'}}
    response = api.post('/api/laporan/report/payment', data={'payment_request_id': str(uuid.uuid4())}, files={'file': ('payment.png', login_background_png(), 'image/png')})
    assert response.status_code == 409
    server.put_object.assert_not_called()


def test_payment_cannot_change_original_team_amount(local_api, monkeypatch):
    api, db = local_api; configure_admin_report(db, monkeypatch)
    db.field_reports.find_one.return_value = {'id':'report', 'payment_amount':'500000.00'}
    response = api.post('/api/laporan/report/payment', data={'payment_request_id': str(uuid.uuid4()), 'payment_amount':'600000'}, files={'file': ('payment.png', login_background_png(), 'image/png')})
    assert response.status_code == 409
    server.put_object.assert_not_called()


def test_officers_cannot_create_reports_or_record_payments(local_api):
    api, db = local_api
    server.app.dependency_overrides.pop(server.admin_required)
    db.users.find_one.return_value = OFFICER
    assert api.get('/api/laporan-options', headers=bearer(OFFICER)).status_code == 403
    assert api.post('/api/laporan', headers=bearer(OFFICER), data=admin_report_data(), files=admin_report_photos()).status_code == 403
    assert api.post('/api/laporan/report/payment', headers=bearer(OFFICER), data={'payment_request_id':str(uuid.uuid4())}, files={'file':('payment.png',login_background_png(),'image/png')}).status_code == 403
    db.field_reports.insert_one.assert_not_called(); db.report_photos.insert_one.assert_not_called()


def test_review_does_not_overwrite_payment_state(local_api):
    api, db = local_api
    db.field_reports.find_one.return_value = {'id':'report','payment_status':'SELESAI','report_status':'SELESAI'}
    assert api.patch('/api/laporan/report/review', json={'catatan_admin':'Review'}).status_code == 200
    assert 'report_status' not in db.field_reports.update_one.call_args.args[1]['$set']
