"""Workflow regression tests; reuse the API fixture without live data."""
from unittest.mock import AsyncMock
from types import SimpleNamespace
import asyncio
import pytest
from test_local_regressions import local_api, server
import storage


@pytest.mark.parametrize("old,new", [("selesai", "dibatalkan"), ("dibatalkan", "kedaluwarsa"), ("kedaluwarsa", "aktif")])
def test_terminal_letter_cannot_modify_new_assignment(local_api, old, new):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"id": "old", "status": old, "assignment_id": "old-assignment"}
    response = api.patch("/api/surat-tugas/old/status", json={"status": new})
    assert response.status_code == 400
    db.accounts.update_many.assert_not_called()
    db.assignments.update_one.assert_not_called()


def test_repeating_terminal_transition_is_idempotent(local_api, monkeypatch):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"id": "old", "status": "selesai"}
    monkeypatch.setattr(server, "enrich_letter", AsyncMock(return_value={"status": "selesai"}))
    assert api.patch("/api/surat-tugas/old/status", json={"status": "selesai"}).status_code == 200
    db.accounts.update_many.assert_not_called()
    db.assignments.update_one.assert_not_called()


def test_concurrent_status_change_returns_conflict(local_api):
    api, db = local_api
    db.assignment_letters.find_one.return_value = {"id": "letter", "status": "aktif"}
    db.assignment_letters.update_one.return_value = SimpleNamespace(matched_count=0)
    assert api.patch("/api/surat-tugas/letter/status", json={"status": "selesai"}).status_code == 409
    db.accounts.update_many.assert_not_called()


def configure_assignment(db, monkeypatch, authority):
    db.users.find_one.return_value = {"id": "officer", "status": "aktif"}
    db.accounts.find_one.return_value = {"id": "unit", "client_id": "client", "surat_kuasa_id": "authority"}
    db.clients.find_one.return_value = {"id": "client", "status": "aktif"}
    db.power_of_attorneys.find_one.return_value = authority
    monkeypatch.setattr(server, "next_sequence", AsyncMock(return_value=1))
    monkeypatch.setattr(server, "build_document_data", AsyncMock(return_value={}))
    monkeypatch.setattr(server, "enrich_letter", AsyncMock(side_effect=lambda letter: letter))


def test_assignment_end_defaults_to_authority_end(local_api, monkeypatch):
    api, db = local_api
    configure_assignment(db, monkeypatch, {"status": "aktif", "tanggal_berakhir": "2099-12-31"})
    result = api.post("/api/penugasan", json={"account_id": "unit", "petugas_id": "officer"})
    assert result.status_code == 200
    assert db.assignments.insert_one.call_args.args[0]["valid_until"] == "2099-12-31"


@pytest.mark.parametrize("authority,end", [({"status": "aktif", "tanggal_berakhir": "2000-01-01"}, None), ({"status": "aktif", "tanggal_berakhir": "2099-01-01"}, "2099-02-01"), ({"status": "aktif", "tanggal_berlaku": "2099-01-01"}, None)])
def test_assignment_must_fit_authority_dates(local_api, monkeypatch, authority, end):
    api, db = local_api
    configure_assignment(db, monkeypatch, authority)
    assert api.post("/api/penugasan", json={"account_id": "unit", "petugas_id": "officer", "valid_until": end}).status_code == 400
    db.assignments.insert_one.assert_not_called()


def test_snapshot_failure_does_not_reserve_unit(local_api, monkeypatch):
    api, db = local_api
    configure_assignment(db, monkeypatch, {"status": "aktif"})
    monkeypatch.setattr(server, "build_document_data", AsyncMock(side_effect=RuntimeError("snapshot failed")))
    with pytest.raises(RuntimeError):
        api.post("/api/penugasan", json={"account_id": "unit", "petugas_id": "officer"})
    db.assignments.insert_one.assert_not_called()


def test_failed_letter_insert_rolls_back_assignment(local_api, monkeypatch):
    api, db = local_api
    configure_assignment(db, monkeypatch, {"status": "aktif"})
    db.assignment_letters.insert_one.side_effect = RuntimeError("letter failed")
    with pytest.raises(RuntimeError):
        api.post("/api/penugasan", json={"account_id": "unit", "petugas_id": "officer"})
    db.assignments.delete_one.assert_awaited_once()
    db.accounts.update_one.assert_not_called()


def test_report_rechecks_revoked_authority(local_api):
    api, db = local_api
    db.assignments.find_one.return_value = {"id": "a", "account_id": "unit", "status": "AKTIF", "power_of_attorney_id": "sk"}
    db.power_of_attorneys.find_one.return_value = {"status": "dicabut"}
    result = api.post("/api/laporan", data={"assignment_id": "a", "account_id": "unit", "status": "TIDAK_DITEMUKAN", "catatan": "Kunjungan telah dilakukan", "latitude": "0", "longitude": "0"})
    assert result.status_code == 400
    db.field_reports.insert_one.assert_not_called()


def test_future_task_explains_reporting_block():
    available = server.task_availability({"status": "AKTIF", "valid_from": "2099-01-01"})
    assert not available["can_report"]
    assert "2099-01-01" in available["blocked_reason"]


def test_used_authority_client_cannot_change(local_api):
    api, db = local_api
    db.clients.find_one.return_value = {"id": "new-client"}
    db.power_of_attorneys.find_one.return_value = {"id": "sk", "client_id": "old-client"}
    db.accounts.find_one.return_value = {"id": "linked-unit"}
    assert api.put("/api/surat-kuasa/sk", json={"nomor": "SK", "client_id": "new-client"}).status_code == 409
    db.power_of_attorneys.update_one.assert_not_called()


def test_unit_history_authority_cannot_change(local_api):
    api, db = local_api
    db.clients.find_one.return_value = {"id": "client"}
    db.power_of_attorneys.find_one.return_value = {"id": "new-sk"}
    db.accounts.find_one.return_value = {"client_id": "client", "surat_kuasa_id": "old-sk"}
    db.assignments.find_one.return_value = {"id": "historical-assignment"}
    result = api.put("/api/akun/unit", json={"nomor_kontrak": "K", "nama_debitur": "Nama", "client_id": "client", "surat_kuasa_id": "new-sk"})
    assert result.status_code == 409
    db.accounts.update_one.assert_not_called()


def test_closed_document_retains_original_snapshot(local_api, monkeypatch):
    api, db = local_api
    snapshot = {"official": "original data"}
    db.assignment_letters.find_one.return_value = {"id": "letter", "company_id": "company-a", "status": "selesai", "document_status": "COMPLETED", "document_snapshot": snapshot}
    result = api.get("/api/surat-tugas/letter/document")
    assert result.status_code == 200
    assert result.json()["data"] == snapshot
    assert result.json()["is_finalized"] is True
    assert result.json()["template"]["company_id"] == "company-a"
    db.document_templates.find_one.assert_awaited_once_with({"company_id": "company-a", "version": "v1"}, {"_id": 0})
    assert api.post("/api/surat-tugas/letter/finalize").status_code == 400


def test_authority_invalid_dates_rejected(local_api):
    api, db = local_api
    assert api.post("/api/surat-kuasa", json={"nomor": "SK", "client_id": "client", "tanggal_berlaku": "2026-10-08", "tanggal_berakhir": "2026-10-01"}).status_code == 400
    db.power_of_attorneys.insert_one.assert_not_called()


def test_invalid_second_photo_does_not_upload_first(local_api, monkeypatch):
    from unittest.mock import Mock
    from test_local_regressions import login_background_png
    api, db = local_api
    uploader = Mock()
    monkeypatch.setattr(server, "put_object", uploader)
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    result = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "UNIT_DITEMUKAN", "catatan": "Foto kunjungan lengkap", "latitude": "0", "longitude": "0"}, files=[("photos", ("valid.png", login_background_png(), "image/png")), ("photos", ("invalid.jpg", b"corrupt", "image/jpeg"))])
    assert result.status_code == 400
    uploader.assert_not_called()


def test_storage_outage_returns_actionable_error_without_report(local_api, monkeypatch):
    from unittest.mock import Mock
    from requests.exceptions import HTTPError
    from test_local_regressions import login_background_png
    api, db = local_api
    monkeypatch.setattr(server, "put_object", Mock(side_effect=HTTPError("remote provider offline")))
    db.assignments.find_one.return_value = {"id": "assignment", "account_id": "unit", "status": "AKTIF"}
    result = api.post("/api/laporan", data={"assignment_id": "assignment", "account_id": "unit", "status": "UNIT_DITEMUKAN", "catatan": "Foto kunjungan lengkap", "latitude": "0", "longitude": "0"}, files={"photos": ("valid.png", login_background_png(), "image/png")})
    assert result.status_code == 503
    assert "Penyimpanan" in result.json()["detail"]
    db.field_reports.insert_one.assert_not_called()


def test_invalid_report_filter_rejected(local_api):
    api, db = local_api
    assert api.get("/api/laporan?tanggal=invalid").status_code == 400


def test_report_filter_uses_wib_midnight(local_api):
    api, db = local_api
    assert api.get("/api/laporan?tanggal=2026-10-08").status_code == 200
    query = db.field_reports.find.call_args.args[0]
    assert query["created_at"] == {"$gte": "2026-10-07T17:00:00+00:00", "$lt": "2026-10-08T17:00:00+00:00"}


def test_local_storage_roundtrip_and_atomic_write(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "LOCAL_STORAGE_DIR", tmp_path.resolve())
    path = "fieldcollector/companies/test/evidence.png"
    assert storage.put_object(path, b"proof", "image/png") == {"path": path}
    assert storage.get_object(path) == (b"proof", "image/png")
    assert len(list((tmp_path / "fieldcollector/companies/test").iterdir())) == 1


def test_expiry_conflict_does_not_disable_healthy_database(local_api, monkeypatch):
    _, db = local_api
    db.command = AsyncMock(return_value={"ok": 1})
    db.assignment_letters.find.return_value.to_list.return_value = [{"id": "expired", "company_id": "company-a"}]
    closer = AsyncMock(side_effect=server.HTTPException(status_code=409, detail="Already closed"))
    monkeypatch.setattr(server, "update_st_status", closer)
    monkeypatch.setattr(server.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server.maintain_database_connection())
    closer.assert_awaited_once()
    assert server.app.state.database_ready is True


@pytest.mark.parametrize("path", ["../outside.jpg", "/outside.jpg", "C:/outside.jpg", "a/../../outside.jpg", "a\\outside.jpg", "a//b.jpg"])
def test_local_storage_rejects_path_escape(tmp_path, monkeypatch, path):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "LOCAL_STORAGE_DIR", tmp_path.resolve())
    with pytest.raises(ValueError):
        storage.put_object(path, b"invalid", "image/jpeg")
    assert not list(tmp_path.iterdir())
