import uuid
from unittest.mock import Mock
import pytest
from test_local_regressions import local_api, server, ADMIN, OFFICER, bearer, login_background_png


def setup(db, monkeypatch):
    leasing = {"id": "leasing", "company_id": ADMIN["company_id"], "nama_perusahaan": "Leasing Contoh"}
    db.clients.find_one.return_value = leasing
    db.clients.find_one_and_update.return_value = leasing
    monkeypatch.setattr(server, "put_object", Mock())


def data(**extra):
    return {"client_id": "leasing", "payment_amount": "1500000.25", "payment_request_id": str(uuid.uuid4()), **extra}


def proof():
    return {"file": ("bukti.png", login_background_png(), "image/png")}


def test_save_and_replay_without_duplicate_upload(local_api, monkeypatch):
    api, db = local_api; setup(db, monkeypatch)
    body = data()
    response = api.post('/api/leasing-payments', data=body, files=proof())
    assert response.status_code == 200
    payment = response.json()
    assert payment['leasing_name'] == 'Leasing Contoh'
    assert payment['payment_amount'] == '1500000.25' and payment['created_at']
    assert payment['url'].startswith('/api/files/')
    assert 'storage_path' not in payment and 'fingerprint' not in payment
    stored = db.documents.insert_one.call_args.args[0]
    assert stored['kind'] == 'leasing_payment' and stored['company_id'] == ADMIN['company_id']
    assert db.clients.find_one.call_args.args[0]['company_id'] == ADMIN['company_id']
    db.documents.find_one.return_value = stored
    server.put_object.reset_mock(); db.documents.insert_one.reset_mock()
    replay = api.post('/api/leasing-payments', data=body, files=proof())
    assert replay.status_code == 200 and replay.json()['id'] == payment['id']
    server.put_object.assert_not_called(); db.documents.insert_one.assert_not_called()
    conflict = api.post('/api/leasing-payments', data={**body, 'payment_amount':'200'}, files=proof())
    assert conflict.status_code == 409


@pytest.mark.parametrize('nominal', ['0', '-1', 'NaN', 'Infinity', '1.234', '1000000000000'])
def test_reject_invalid_amount_before_storage(local_api, monkeypatch, nominal):
    api, db = local_api; setup(db, monkeypatch)
    assert api.post('/api/leasing-payments', data=data(payment_amount=nominal), files=proof()).status_code == 400
    server.put_object.assert_not_called()


def test_missing_leasing_and_invalid_evidence(local_api, monkeypatch):
    api, db = local_api; setup(db, monkeypatch)
    db.clients.find_one.return_value = None
    assert api.post('/api/leasing-payments', data=data(), files=proof()).status_code == 404
    assert api.post('/api/leasing-payments', data=data(), files={'file':('bad.pdf',b'bad','application/pdf')}).status_code == 400
    assert api.post('/api/leasing-payments', data=data()).status_code == 422
    server.put_object.assert_not_called()


def test_listing_paginated_and_scoped(local_api):
    api, db = local_api
    cursor = db.documents.find.return_value
    cursor.limit.return_value = cursor
    cursor.to_list.return_value = [{'id':'a','kind':'leasing_payment','storage_path':'secret','created_at':'2026-10-17'}, {'id':'b'}]
    response = api.get('/api/leasing-payments?limit=1&page=2')
    assert response.status_code == 200
    assert response.json() == {'items':[{'id':'a','created_at':'2026-10-17'}], 'next_page':3}
    assert db.documents.find.call_args.args[0] == {'company_id':ADMIN['company_id'], 'kind':'leasing_payment'}
    cursor.skip.assert_called_once_with(1)


def test_officer_cannot_create_list_or_open_payment_proof(local_api, monkeypatch):
    api, db = local_api; setup(db, monkeypatch)
    server.app.dependency_overrides.pop(server.admin_required)
    db.users.find_one.return_value = OFFICER
    assert api.get('/api/leasing-payments', headers=bearer(OFFICER)).status_code == 403
    assert api.post('/api/leasing-payments', headers=bearer(OFFICER), data=data(), files=proof()).status_code == 403
    db.documents.find_one.return_value = {'kind':'leasing_payment','company_id':OFFICER['company_id']}
    assert api.get('/api/files/proof.png', headers=bearer(OFFICER)).status_code == 404
    server.get_object.assert_not_called(); server.put_object.assert_not_called()


def test_payment_prevents_leasing_deletion(local_api):
    api, db = local_api
    db.clients.find_one.return_value = {'id':'leasing'}
    db.documents.find_one.return_value = {'kind':'leasing_payment','client_id':'leasing'}
    assert api.delete('/api/clients/leasing').status_code == 409
    db.clients.delete_one.assert_not_called()
