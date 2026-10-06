"""Tests for the new Surat Penugasan + BASTK dynamic document feature.

Covers: GET /api/surat-tugas/{id}/document, POST /finalize (idempotent),
snapshot immutability vs petugas edit, PUT /company number_format,
public verify by generate_code (no debtor leak), QR endpoint,
petugas new fields, account stnk_name, cancel letter -> DIBATALKAN.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@demo.com", "password": "admin123"}


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def seed_ids(admin_h):
    """Create a fresh client + SK + account + petugas + penugasan for isolated testing."""
    suffix = uuid.uuid4().hex[:6].upper()
    # Client
    r = requests.post(f"{API}/clients", headers=admin_h, json={
        "nama_perusahaan": f"TEST_PT_{suffix}", "nama_pic": "PIC", "email": "pic@test.com",
        "nomor_pic": "021", "alamat": "Jl Test", "status": "aktif"
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    client_id = r.json()["id"]
    # SK
    r = requests.post(f"{API}/surat-kuasa", headers=admin_h, json={
        "client_id": client_id, "nomor": f"TEST/SK/{suffix}", "tanggal_surat": "2026-01-01",
        "tanggal_berlaku": "2026-01-01", "tanggal_berakhir": "2026-12-31", "status": "aktif"
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    sk_id = r.json()["id"]
    # Account
    r = requests.post(f"{API}/akun", headers=admin_h, json={
        "nomor_kontrak": f"TEST-KON-{suffix}", "nama_debitur": "TEST_Debitur_Secret",
        "nik": "SECRET_NIK_1234567890", "telepon": "081234567890", "alamat": "SECRET_ADDR",
        "nomor_polisi": "B 1234 TST", "nomor_rangka": "SECRET_CHASSIS_X",
        "nomor_mesin": "SECRET_ENGINE_Y", "warna": "Hitam", "tahun": "2022",
        "merk": "Honda", "model": "Vario", "jenis_kendaraan": "Motor",
        "stnk_name": "STNK Owner Test",
        "client_id": client_id, "surat_kuasa_id": sk_id,
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    acc_id = r.json()["id"]
    # Petugas - create new to avoid disturbing demo officer
    petugas_email = f"test_officer_{suffix.lower()}@test.com"
    r = requests.post(f"{API}/petugas", headers=admin_h, json={
        "name": f"TEST_Officer_{suffix}", "email": petugas_email, "password": "testpass123",
        "telepon": "0811", "tim": "A", "nik": "9999888877776666",
        "jabatan": "PROFCOLL", "no_sertifikasi": "CERT-1234567",
        "sertifikasi_valid_until": "2027-12-31",
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    petugas_id = r.json()["id"]
    # Penugasan -> Surat Tugas
    r = requests.post(f"{API}/penugasan", headers=admin_h, json={
        "petugas_id": petugas_id, "account_ids": [acc_id],
        "tanggal_tugas": "2026-01-15", "masa_berlaku": "2026-02-15",
        "catatan": "test",
    }, timeout=20)
    assert r.status_code in (200, 201), r.text
    letter_id = r.json()["id"]
    return {
        "client_id": client_id, "sk_id": sk_id, "acc_id": acc_id,
        "petugas_id": petugas_id, "letter_id": letter_id, "suffix": suffix,
    }


# --------------------- GET document (DRAFT) ---------------------
class TestDocumentDraft:
    def test_document_draft_structure(self, admin_h, seed_ids):
        r = requests.get(f"{API}/surat-tugas/{seed_ids['letter_id']}/document", headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["document_status"] == "DRAFT"
        assert d["is_finalized"] is False
        data = d["data"]
        assert data["company"]["name"]
        assert data["officer"]["nik"] == "9999888877776666"
        assert data["officer"]["certification_number"] == "CERT-1234567"
        assert data["officer"]["position"] == "PROFCOLL"
        assert len(data["accounts"]) == 1
        acc = data["accounts"][0]
        assert acc["license_plate"] == "B 1234 TST"
        assert acc["chassis_number"] == "SECRET_CHASSIS_X"
        assert acc["engine_number"] == "SECRET_ENGINE_Y"
        assert acc["stnk_name"] == "STNK Owner Test"


# --------------------- Company config + Finalize + Verify + Cancel ---------------------
class TestFinalizeAndFormat:
    def test_update_company_format(self, admin_h):
        # fetch original
        r = requests.get(f"{API}/company", headers=admin_h, timeout=20)
        assert r.status_code == 200
        orig = r.json()
        payload = {
            "nama": orig.get("nama", "PT Test"),
            "alamat": orig.get("alamat", ""), "telepon": orig.get("telepon", ""),
            "email": orig.get("email", ""), "city": orig.get("city", "JAKARTA"),
            "director_name": orig.get("director_name", "DIR"),
            "director_position": orig.get("director_position", "DIREKTUR"),
            "company_code": "GKN",
            "number_format": "{sequence}/{company_code}/{month_name}/{year}",
            "logo": orig.get("logo", ""),
        }
        r = requests.put(f"{API}/company", headers=admin_h, json=payload, timeout=20)
        assert r.status_code == 200, r.text

    def test_full_finalize_verify_cancel_flow(self, admin_h, seed_ids):
        """Combined flow test: finalize -> idempotent -> QR -> public verify (no leak) -> cancel -> DIBATALKAN."""
        lid = seed_ids["letter_id"]

        # 1. FINALIZE
        r = requests.post(f"{API}/surat-tugas/{lid}/finalize", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_finalized"] is True
        assert d["document_status"] == "ACTIVE"
        docnum = d["data"]["letter"]["document_number"]
        gcode = d["data"]["letter"]["generate_code"]
        reg = d["data"]["letter"]["register_number"]
        assert docnum and "/GKN/" in docnum, f"document_number format wrong: {docnum}"
        assert gcode and gcode.startswith("GNR-"), gcode
        assert reg and "/" in reg

        # 2. Idempotent re-finalize
        r2 = requests.post(f"{API}/surat-tugas/{lid}/finalize", headers=admin_h, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["data"]["letter"]["document_number"] == docnum
        assert d2["data"]["letter"]["generate_code"] == gcode

        # 3. QR endpoint (public, no auth)
        r = requests.get(f"{API}/surat-tugas/{lid}/qr", timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

        # 4. Public verify by generate_code
        r = requests.get(f"{API}/public/verify/{gcode}", timeout=20)
        assert r.status_code == 200, r.text
        pd = r.json()
        assert pd["valid"] is True
        assert pd["doc_status"] == "VALID"
        assert pd["generate_code"] == gcode
        assert pd["nomor"] == docnum
        assert pd["company_name"]
        assert "valid_until" in pd
        # Debtor data must NOT be leaked
        payload_str = str(pd).lower()
        for secret in ("test_debitur_secret", "secret_nik", "secret_addr",
                       "secret_chassis", "secret_engine", "081234567890", "b 1234 tst"):
            assert secret.lower() not in payload_str, f"Leaked field found: {secret}"
        for banned in ("debtor_name", "debtor_nik", "debtor_address", "debtor_phone",
                       "chassis_number", "engine_number", "accounts"):
            assert banned not in pd, f"Public verify leaked key: {banned}"

        # 5. Cancel letter -> public verify shows DIBATALKAN
        r = requests.patch(f"{API}/surat-tugas/{lid}/status", headers=admin_h,
                           json={"status": "dibatalkan"}, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/public/verify/{gcode}", timeout=20)
        assert r.status_code == 200
        cd = r.json()
        assert cd["doc_status"] == "DIBATALKAN"
        assert cd["valid"] is False


# --------------------- Snapshot immutability ---------------------
class TestSnapshotImmutability:
    def test_officer_rename_does_not_affect_snapshot(self, admin_h, seed_ids):
        """Finalize the letter in a separate petugas/account to isolate from other tests."""
        # Finalize this fixture's letter first (fixture is per-worker so fresh)
        lid = seed_ids["letter_id"]
        r = requests.post(f"{API}/surat-tugas/{lid}/finalize", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        pid = seed_ids["petugas_id"]
        r = requests.get(f"{API}/petugas/{pid}", headers=admin_h, timeout=20)
        assert r.status_code == 200
        p = r.json()
        orig_name = p["name"]
        new_name = f"CHANGED_{uuid.uuid4().hex[:4]}"
        r = requests.put(f"{API}/petugas/{pid}", headers=admin_h, json={
            "name": new_name, "email": p["email"], "telepon": p.get("telepon", ""),
            "tim": p.get("tim", ""), "status": p.get("status", "aktif"),
            "nik": p.get("nik", ""), "jabatan": p.get("jabatan", "PROFCOLL"),
            "no_sertifikasi": p.get("no_sertifikasi", ""),
            "sertifikasi_valid_until": p.get("sertifikasi_valid_until", ""),
        }, timeout=20)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/surat-tugas/{lid}/document", headers=admin_h, timeout=20)
        assert r.status_code == 200
        snap_name = r.json()["data"]["officer"]["name"]
        assert snap_name == orig_name, f"Snapshot leaked new name: expected {orig_name}, got {snap_name}"


# --------------------- Public verify unknown ---------------------
class TestPublicVerify:
    def test_public_verify_unknown(self):
        r = requests.get(f"{API}/public/verify/GNR-UNKNOWN-XYZ", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is False
        assert d["doc_status"] == "TIDAK DITEMUKAN"
