"""Local API regression tests. No MongoDB, storage, or remote demo required."""
import os
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "audit_tests")
os.environ.setdefault("JWT_SECRET", "local-regression-test-secret-32-bytes")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from pymongo.errors import DuplicateKeyError

def login_background_png():
    import io
    from PIL import Image
    output = io.BytesIO()
    Image.new("RGBA", (64, 32), (0, 120, 255, 180)).save(output, format="PNG")
    return output.getvalue()

@pytest.mark.parametrize("preset", ["aurora", "blueprint", "sunrise"])
def test_login_background_preset_persists_in_company_scope(local_api, preset):
    api, database = local_api
    database.companies.find_one.return_value = {"id": "company-a"}
    response = api.put("/api/company/login-background", json={"preset": preset})
    assert response.status_code == 200
    query, update = database.companies.update_one.call_args.args
    assert query == {"id": "company-a"}
    assert update["$set"]["login_background.preset"] == preset

def test_login_image_requires_upload(local_api):
    api, database = local_api
    database.companies.find_one.return_value = {"id": "company-a"}
    assert api.put("/api/company/login-background", json={"preset": "image"}).status_code == 400
    database.companies.update_one.assert_not_called()

def test_login_background_upload_normalizes_image(local_api):
    api, database = local_api
    database.companies.find_one.return_value = {"id": "company-a"}
    response = api.post("/api/company/login-background", files={"file": ("background.png", login_background_png(), "image/png")})
    assert response.status_code == 200
    query, update = database.companies.update_one.call_args.args
    assert query == {"id": "company-a"}
    background = update["$set"]["login_background"]
    assert background["preset"] == "image"
    assert background["image"].startswith("data:image/jpeg;base64,")
    assert background["version"]

@pytest.mark.parametrize("content,mime", [(b"not an image", "image/jpeg"), (b"<svg></svg>", "image/svg+xml"), (b"x" * (3 * 1024 * 1024 + 1), "image/jpeg")], ids=["corrupt", "svg", "too-large"])
def test_login_background_rejects_invalid_upload(local_api, content, mime):
    api, database = local_api
    database.companies.find_one.return_value = {"id": "company-a"}
    assert api.post("/api/company/login-background", files={"file": ("background", content, mime)}).status_code == 400
    database.companies.update_one.assert_not_called()

def test_login_background_reset_clears_uploaded_image(local_api):
    api, database = local_api
    database.companies.find_one.return_value = {"id": "company-a", "login_background": {"preset": "image", "image": "old"}}
    assert api.put("/api/company/login-background", json={"preset": "aurora", "reset_image": True}).status_code == 200
    assert database.companies.update_one.call_args.args[1]["$set"]["login_background.image"] == ""

def test_public_branding_returns_background_url_without_image_payload(local_api):
    api, database = local_api
    database.companies.find_one.return_value = {"login_background": {"preset": "image", "image": "private-sized-image", "version": "abc"}}
    result = api.get("/api/branding").json()
    assert result["login_background"] == {"preset": "image", "image_url": "/api/branding/login-background?v=abc"}
    assert "private-sized-image" not in str(result)

def test_login_background_settings_reject_officers(local_api):
    api, database = local_api
    server.app.dependency_overrides.pop(server.admin_required)
    database.users.find_one.return_value = OFFICER
    assert api.put("/api/company/login-background", json={"preset": "aurora"}, headers=bearer(OFFICER)).status_code == 403
    assert api.post("/api/company/login-background", files={"file": ("bg.png", login_background_png(), "image/png")}, headers=bearer(OFFICER)).status_code == 403
    database.companies.update_one.assert_not_called()

ADMIN = {"id": "admin", "company_id": "company-a", "role": "admin", "status": "aktif", "name": "Admin"}
OFFICER = {**ADMIN, "id": "officer", "role": "petugas"}


@pytest.fixture
def local_api(monkeypatch):
    monkeypatch.setattr(server.transactions, "ENABLED", False)
    monkeypatch.setattr(server.app.state, "database_ready", True)
    collections = {}
    for name in ("users", "idempotency", "rate_limits", "revoked_tokens", "upload_intents", "report_photos", "field_reports", "documents", "document_templates", "assignments", "assignment_letters", "accounts", "clients", "power_of_attorneys", "debtors", "audit_logs", "companies", "login_attempts"):
        cursor = Mock()
        cursor.to_list = AsyncMock(return_value=[])
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        collections[name] = SimpleNamespace(find_one=AsyncMock(return_value=None), find_one_and_update=AsyncMock(return_value={"count": 1}), find=Mock(return_value=cursor), count_documents=AsyncMock(return_value=0), distinct=AsyncMock(return_value=[]), insert_one=AsyncMock(), update_one=AsyncMock(), update_many=AsyncMock(), create_index=AsyncMock(), delete_one=AsyncMock())
    database = SimpleNamespace(**collections)
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setattr(server, "get_object", Mock(return_value=(b"photo", "image/jpeg")))
    server.app.dependency_overrides[server.admin_required] = lambda: ADMIN
    server.app.dependency_overrides[server.petugas_required] = lambda: OFFICER
    # Do not enter TestClient context: startup requires a real deployment database.
    api = TestClient(server.app)
    yield api, database
    api.close()
    server.app.dependency_overrides.clear()


def bearer(user=ADMIN):
    return {"Authorization": "Bearer " + server.create_access_token(user["id"], user["role"])}


@pytest.mark.parametrize("user,owner,expected", [
    (ADMIN, {"id": "report"}, 200),
    (ADMIN, None, 404),
    (OFFICER, {"id": "report"}, 200),
    (OFFICER, None, 404),
    ({**ADMIN, "status": "nonaktif"}, None, 403),
])
def test_photo_authorization(local_api, user, owner, expected):
    api, db = local_api
    db.users.find_one.return_value = user
    db.report_photos.find_one.return_value = {"report_id": "report"}
    db.field_reports.find_one.return_value = owner
    response = api.get("/api/files/photo.jpg", headers=bearer(user))
    assert response.status_code == expected
    if expected in (200, 404):
        query = db.field_reports.find_one.call_args.args[0]
        assert query["company_id"] == "company-a"
        if user["role"] == "petugas":
            assert query["petugas_id"] == "officer"
    if expected == 200:
        assert response.headers["cache-control"] == "private, no-store"
    else:
        server.get_object.assert_not_called()


def test_document_from_other_company_hidden(local_api):
    api, db = local_api
    db.users.find_one.return_value = ADMIN
    assert api.get("/api/files/other.pdf", headers=bearer()).status_code == 404
    assert db.documents.find_one.call_args.args[0]["company_id"] == "company-a"
    server.get_object.assert_not_called()


@pytest.mark.parametrize("payload", [{"role": "admin"}, {"sub": "admin", "type": "refresh"}])
@pytest.mark.parametrize("route", ["/api/auth/me", "/api/files/photo.jpg"])
def test_malformed_signed_token_returns_401(local_api, payload, route):
    api, db = local_api
    token = jwt.encode(payload, server.JWT_SECRET, algorithm="HS256")
    assert api.get(route, headers={"Authorization": f"Bearer {token}"}).status_code == 401
    db.users.find_one.assert_not_called()


@pytest.mark.parametrize("coordinates", [
    {"latitude": "abc", "longitude": "106"},
    {"latitude": "nan", "longitude": "106"},
    {"latitude": "0", "longitude": "inf"},
    {"latitude": "91", "longitude": "106"},
    {"latitude": "0", "longitude": "181"},
    {"latitude": "0", "lokasi_alasan": "GPS gagal"},
    {"lokasi_alasan": "x"},
])
def test_invalid_location_is_400_not_500(local_api, coordinates):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", **coordinates})
    assert response.status_code == 400
    db.field_reports.insert_one.assert_not_called()


@pytest.mark.parametrize("location", [{"latitude": "0", "longitude": "0"}, {"lokasi_alasan": "GPS tidak tersedia"}])
def test_valid_report_saved(local_api, location):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", **location})
    assert response.status_code == 200
    assert response.json()["latitude"] == (0 if "latitude" in location else None)
    db.field_reports.insert_one.assert_awaited_once()


def test_reviewed_report_cannot_be_resubmitted(local_api):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    db.field_reports.find_one.return_value = {"report_status": "REVIEWED"}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", "latitude": "0", "longitude": "0"})
    assert response.status_code == 400
    assert db.field_reports.find_one.call_args.args[0] == {"assignment_id": "assignment"}
    db.field_reports.insert_one.assert_not_called()


@pytest.mark.parametrize("status", ["UNKNOWN", "aktif"])
def test_invalid_or_reactivated_letter_rejected(local_api, status):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"status": "dibatalkan"}
    assert api.patch("/api/surat-tugas/letter/status", json={"status": status}).status_code == 400
    db.assignment_letters.update_one.assert_not_called()


def test_cross_company_account_reference_rejected(local_api):
    api, db = local_api
    response = api.post("/api/akun", json={"nomor_kontrak": "123", "nama_debitur": "Test", "client_id": "foreign-client", "surat_kuasa_id": "foreign-sk"})
    assert response.status_code == 400
    assert db.clients.find_one.call_args.args[0]["company_id"] == "company-a"
    db.accounts.insert_one.assert_not_called()


@pytest.mark.parametrize("params", [{"page": 0}, {"limit": 0}, {"limit": 1001}])
def test_invalid_pagination_rejected(local_api, params):
    api, _ = local_api
    assert api.get("/api/akun", params=params).status_code == 422


def test_duplicate_officer_email_rejected(local_api):
    api, db = local_api
    db.users.find_one.return_value = {"id": "someone-else"}
    assert api.put("/api/petugas/officer", json={"name": "Officer", "email": "taken@example.com"}).status_code == 400
    db.users.update_one.assert_not_called()


def test_new_officer_requires_password(local_api):
    api, db = local_api
    assert api.post("/api/petugas", json={"name": "Officer", "email": "new@example.com"}).status_code == 400
    db.users.insert_one.assert_not_called()


def test_unknown_report_status_rejected(local_api):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "UNKNOWN", "catatan": "Catatan kunjungan lengkap", "latitude": "0", "longitude": "0"})
    assert response.status_code == 400
    db.field_reports.insert_one.assert_not_called()


def test_fake_image_rejected_before_storage(local_api, monkeypatch):
    api, db = local_api
    upload = Mock()
    monkeypatch.setattr(server, "put_object", upload)
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "UNIT_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", "latitude": "0", "longitude": "0"}, files={"photos": ("fake.jpg", b"not an image", "image/jpeg")})
    assert response.status_code == 400
    upload.assert_not_called()
    db.field_reports.insert_one.assert_not_called()


def test_concurrent_duplicate_submission_is_400(local_api):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    db.field_reports.insert_one.side_effect = DuplicateKeyError("submission_key collision")
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", "latitude": "0", "longitude": "0"})
    assert response.status_code == 400
    db.accounts.update_one.assert_not_called()


@pytest.mark.parametrize("dates", [
    {"valid_from": "2099-01-01"},
    {"valid_until": "2000-01-01"},
    {"valid_from": "invalid"},
])
def test_report_outside_assignment_dates_rejected(local_api, dates):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF", **dates}
    response = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Catatan kunjungan lengkap", "latitude": "0", "longitude": "0"})
    assert response.status_code == 400
    db.field_reports.insert_one.assert_not_called()


@pytest.mark.parametrize("route", ["/api/public/verify/code", "/api/public/surat-tugas/letter"])
def test_expired_letter_is_not_publicly_valid(local_api, route):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"id": "letter", "petugas_id": "officer", "company_id": "company-a", "nomor": "001", "status": "aktif", "masa_berlaku": "2000-01-01"}
    db.companies = SimpleNamespace(find_one=AsyncMock(return_value=None))
    response = api.get(route)
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_concurrent_assignment_collision_rejected(local_api, monkeypatch):
    api, db = local_api
    db.users.find_one.return_value = OFFICER
    db.accounts.find_one.return_value = {"id": "unit", "client_id": "client", "surat_kuasa_id": "sk"}
    db.power_of_attorneys.find_one.return_value = {"status": "aktif"}
    db.assignments.insert_one.side_effect = DuplicateKeyError("active_key collision")
    monkeypatch.setattr(server, "next_sequence", AsyncMock(return_value=1))
    response = api.post("/api/penugasan", json={"petugas_id": "officer", "account_id": "unit"})
    assert response.status_code == 400
    db.assignment_letters.insert_one.assert_not_called()


def test_terminal_assignment_releases_active_key(local_api, monkeypatch):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"id": "letter", "status": "aktif", "assignment_id": "assignment"}
    monkeypatch.setattr(server, "enrich_letter", AsyncMock(return_value={}))
    assert api.patch("/api/surat-tugas/letter/status", json={"status": "selesai"}).status_code == 200
    update = db.assignments.update_one.call_args.args[1]
    assert update["$unset"] == {"active_key": ""}
    assert update["$set"]["status"] == "SELESAI"
    query, release = db.accounts.update_many.call_args.args
    assert query["company_id"] == "company-a"
    assert release["$set"]["status"] == "BELUM_DITUGASKAN"
    assert db.assignment_letters.update_one.call_args.args[1]["$set"]["document_status"] == "COMPLETED"


def test_startup_does_not_seed_without_explicit_opt_in(local_api, monkeypatch):
    _, db = local_api
    import seed
    seeder = AsyncMock()
    monkeypatch.setattr(seed, "seed_all", seeder)
    monkeypatch.setattr(server, "init_storage", Mock())
    monkeypatch.setattr(server, "migrate_assignments_non_destructive", AsyncMock())
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    asyncio.run(server.initialize_database())
    seeder.assert_not_called()
    db.field_reports.create_index.assert_any_await("submission_key", unique=True, sparse=True)
    db.assignments.create_index.assert_any_await("active_key", unique=True, sparse=True)


def test_expired_login_lock_resets_attempt_count(local_api, monkeypatch):
    api, db = local_api
    db.login_attempts.find_one.return_value = {"count": 5, "locked_until": "2000-01-01T00:00:00+00:00"}
    response = api.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    assert response.status_code == 401
    db.login_attempts.delete_one.assert_awaited_once()


@pytest.mark.parametrize("route,body", [
    ("/api/clients", {"nama_perusahaan": "Client", "status": "UNKNOWN"}),
    ("/api/petugas", {"name": "Officer", "email": "new@example.com", "status": "UNKNOWN"}),
    ("/api/akun", {"nomor_kontrak": "123", "nama_debitur": "Test", "client_id": "client", "surat_kuasa_id": "sk", "latitude": 91}),
])
def test_invalid_model_values_rejected(local_api, route, body):
    api, _ = local_api
    assert api.post(route, json=body).status_code == 422


def test_account_enrichment_scopes_legacy_references(local_api):
    _, db = local_api
    account = {"id": "unit", "company_id": "company-a", "client_id": "foreign-client", "surat_kuasa_id": "foreign-sk"}
    result = asyncio.run(server.enrich_account(account))
    assert result["client_name"] == "-"
    assert db.clients.find_one.call_args.args[0]["company_id"] == "company-a"
    assert db.power_of_attorneys.find_one.call_args.args[0]["company_id"] == "company-a"
    assert db.assignment_letters.find_one.call_args.args[0]["company_id"] == "company-a"


@pytest.mark.parametrize("endpoint,collection", [("clients", "clients"), ("surat-kuasa", "power_of_attorneys"), ("akun", "accounts"), ("petugas", "users")])
def test_admin_delete_unused_is_scoped_and_audited(local_api, endpoint, collection):
    api, database = local_api
    target = getattr(database, collection)
    target.find_one.return_value = {"id": "record"}
    assert api.delete(f"/api/{endpoint}/record").status_code == 200
    scope = target.delete_one.call_args.args[0]
    assert scope["company_id"] == "company-a"
    assert scope["id"] == "record"
    if endpoint == "petugas":
        assert scope["role"] == "petugas"
    database.audit_logs.insert_one.assert_called_once()

@pytest.mark.parametrize("endpoint,collection", [("clients", "clients"), ("surat-kuasa", "power_of_attorneys"), ("akun", "accounts"), ("petugas", "users")])
def test_delete_missing_or_other_tenant_record_is_404(local_api, endpoint, collection):
    api, database = local_api
    assert api.delete(f"/api/{endpoint}/missing").status_code == 404
    getattr(database, collection).delete_one.assert_not_called()

@pytest.mark.parametrize("endpoint,collection,reference,field", [
    ("clients", "clients", "power_of_attorneys", "client_id"),
    ("surat-kuasa", "power_of_attorneys", "accounts", "surat_kuasa_id"),
    ("akun", "accounts", "assignments", "account_id"),
    ("petugas", "users", "field_reports", "petugas_id"),
])
def test_delete_rejects_referenced_data(local_api, endpoint, collection, reference, field):
    api, database = local_api
    getattr(database, collection).find_one.return_value = {"id": "record"}
    getattr(database, reference).find_one.return_value = {"id": "history"}
    assert api.delete(f"/api/{endpoint}/record").status_code == 409
    getattr(database, collection).delete_one.assert_not_called()
    assert getattr(database, reference).find_one.call_args.args[0] == {"company_id": "company-a", field: "record"}

@pytest.mark.parametrize("endpoint", ["clients", "surat-kuasa", "akun", "petugas"])
def test_officer_cannot_delete_admin_data(local_api, endpoint):
    api, database = local_api
    server.app.dependency_overrides.pop(server.admin_required)
    database.users.find_one.return_value = OFFICER
    assert api.delete(f"/api/{endpoint}/record", headers=bearer(OFFICER)).status_code == 403


@pytest.mark.parametrize("status", ["aktif", "nonaktif", "berakhir", "dicabut"])
def test_surat_kuasa_accepts_statuses_exposed_by_admin_ui(status):
    assert server.SuratKuasaInput(nomor="SK-1", client_id="client", status=status).status == status


def test_database_outage_returns_503_and_cors_instead_of_network_failure(local_api):
    api, database = local_api
    server.app.state.database_ready = False
    response = api.post("/api/auth/login", json={"email": "admin@example.com", "password": "test"}, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 503
    assert "dipulihkan" in response.json()["detail"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["retry-after"] == "15"
    database.users.find_one.assert_not_called()
    assert api.get("/api/health").status_code == 503


def test_database_ready_health_reports_success(local_api):
    api, _ = local_api
    assert api.get("/api/health").json() == {"status": "ready", "database": "ready"}


def test_database_outage_allows_cors_preflight(local_api):
    api, _ = local_api
    server.app.state.database_ready = False
    response = api.options("/api/auth/login", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200


def test_database_monitor_recovers_after_failed_connection(local_api, monkeypatch):
    _, database = local_api
    server.app.state.database_ready = False
    database.command = AsyncMock(side_effect=[server.ConnectionFailure("offline"), {"ok": 1}])
    initializer = AsyncMock()
    monkeypatch.setattr(server, "initialize_database", initializer)
    monkeypatch.setattr(server.asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()]))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server.maintain_database_connection())
    initializer.assert_awaited_once()
    assert server.app.state.database_ready is True
    assert database.command.await_count == 2


def test_database_disconnect_during_login_returns_service_unavailable(local_api):
    api, database = local_api
    database.users.find_one.side_effect = server.ConnectionFailure("offline")
    response = api.post("/api/auth/login", json={"email": "admin@example.com", "password": "test"})
    assert response.status_code == 503
    assert "dipulihkan" in response.json()["detail"]
    assert server.app.state.database_ready is False
