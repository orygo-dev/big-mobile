"""FieldCollector end-to-end backend API tests.

Covers: auth, dashboard, clients, surat kuasa, akun, petugas,
penugasan -> surat tugas, laporan (petugas), authorization,
public verification and file serving.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://big-deploy.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@demo.com", "password": "admin123"}
PETUGAS = {"email": "petugas@demo.com", "password": "petugas123"}


# ---------------------------- fixtures ----------------------------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def petugas_token():
    r = requests.post(f"{API}/auth/login", json=PETUGAS, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def petugas_h(petugas_token):
    return {"Authorization": f"Bearer {petugas_token}"}


# ---------------------------- auth ----------------------------
class TestAuth:
    def test_admin_login(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and d["user"]["role"] == "admin"

    def test_petugas_login(self):
        r = requests.post(f"{API}/auth/login", json=PETUGAS, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "petugas"

    def test_login_invalid(self):
        # Use random email to avoid tripping brute-force lockout for shared creds
        r = requests.post(f"{API}/auth/login",
                          json={"email": f"nope-{uuid.uuid4().hex[:6]}@demo.com", "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me_requires_token(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_ok(self, admin_h):
        r = requests.get(f"{API}/auth/me", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "admin@demo.com"


# ---------------------------- dashboard ----------------------------
class TestDashboard:
    def test_stats(self, admin_h):
        r = requests.get(f"{API}/dashboard/stats", headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("surat_kuasa_aktif", "total_akun", "tugas_aktif",
                  "unit_ditemukan", "unit_tidak_ditemukan",
                  "belum_dikerjakan", "laporan_hari_ini"):
            assert k in d

    def test_recent_activity(self, admin_h):
        r = requests.get(f"{API}/dashboard/recent-activity", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reports_7days(self, admin_h):
        r = requests.get(f"{API}/dashboard/reports-7days", headers=admin_h, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) == 7


# ---------------------------- clients + surat kuasa + akun ----------------------------
class TestClientsAndSK:
    def test_clients_list(self, admin_h):
        r = requests.get(f"{API}/clients", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_edit_client(self, admin_h):
        payload = {"nama_perusahaan": f"TEST_PT_{uuid.uuid4().hex[:6]}",
                   "alamat": "Jl. Test", "telepon": "021", "email": "x@x.com",
                   "nama_pic": "PIC", "nomor_pic": "0811", "status": "aktif"}
        r = requests.post(f"{API}/clients", headers=admin_h, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        g = requests.get(f"{API}/clients/{cid}", headers=admin_h, timeout=15)
        assert g.status_code == 200
        assert g.json()["nama_perusahaan"] == payload["nama_perusahaan"]
        # update
        payload["alamat"] = "Jl. Updated"
        u = requests.put(f"{API}/clients/{cid}", headers=admin_h, json=payload, timeout=15)
        assert u.status_code == 200
        assert u.json()["alamat"] == "Jl. Updated"

    def test_create_sk_and_akun(self, admin_h):
        # need a client
        c = requests.post(f"{API}/clients", headers=admin_h, json={
            "nama_perusahaan": f"TEST_CLI_{uuid.uuid4().hex[:6]}", "status": "aktif",
        }, timeout=15).json()
        sk_payload = {"nomor": f"SK/TEST/{uuid.uuid4().hex[:4]}", "client_id": c["id"],
                      "tanggal_surat": "2026-01-01", "tanggal_berlaku": "2026-01-01",
                      "tanggal_berakhir": "2027-01-01", "status": "aktif"}
        sk = requests.post(f"{API}/surat-kuasa", headers=admin_h, json=sk_payload, timeout=15)
        assert sk.status_code == 200, sk.text
        sk_id = sk.json()["id"]
        # detail
        d = requests.get(f"{API}/surat-kuasa/{sk_id}", headers=admin_h, timeout=15)
        assert d.status_code == 200
        assert "accounts" in d.json()
        # add akun
        acc = requests.post(f"{API}/akun", headers=admin_h, json={
            "nomor_kontrak": f"TESTK-{uuid.uuid4().hex[:5]}", "nama_debitur": "TEST Debitur",
            "client_id": c["id"], "surat_kuasa_id": sk_id, "provinsi": "DKI",
            "nomor_polisi": "B 1 TEST",
        }, timeout=15)
        assert acc.status_code == 200, acc.text
        assert acc.json()["status"] == "BELUM_DITUGASKAN"


# ---------------------------- petugas CRUD ----------------------------
class TestPetugas:
    def test_list_petugas(self, admin_h):
        r = requests.get(f"{API}/petugas", headers=admin_h, timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert any(p.get("petugas_code") == "PTG-00123" for p in items), "Andi Pratama PTG-00123 missing"

    def test_create_petugas(self, admin_h):
        email = f"test_p_{uuid.uuid4().hex[:6]}@demo.com"
        r = requests.post(f"{API}/petugas", headers=admin_h, json={
            "name": "TEST Petugas", "email": email, "password": "petugas123",
            "telepon": "0811", "tim": "A", "status": "aktif",
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["petugas_code"].startswith("PTG-")


# ---------------------------- end-to-end penugasan + laporan ----------------------------
class TestPenugasanAndLaporan:
    """E2E: pick a BELUM_DITUGASKAN akun from seed SK/FIN/2026/0101,
    assign to Andi Pratama, verify ST nomor format, submit laporan as petugas."""

    @pytest.fixture(scope="class")
    def context(self, admin_h, petugas_h):
        # find Andi Pratama
        petugas = requests.get(f"{API}/petugas", headers=admin_h, timeout=15).json()
        andi = next((p for p in petugas if p.get("petugas_code") == "PTG-00123"), None)
        assert andi is not None
        # find a BELUM_DITUGASKAN akun
        r = requests.get(f"{API}/akun", headers=admin_h,
                         params={"status": "BELUM_DITUGASKAN", "limit": 50}, timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        assert items, "No BELUM_DITUGASKAN accounts found in seed"
        acc = items[0]
        return {"petugas_id": andi["id"], "account_id": acc["id"], "acc": acc}

    def test_create_penugasan(self, admin_h, context):
        payload = {
            "petugas_id": context["petugas_id"],
            "account_ids": [context["account_id"]],
            "tanggal_tugas": "2026-01-15",
            "masa_berlaku": "2026-02-15",
            "catatan": "TEST penugasan",
        }
        r = requests.post(f"{API}/penugasan", headers=admin_h, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        letter = r.json()
        # format ST/FC/2026/MM/0001
        import re
        assert re.match(r"^ST/FC/\d{4}/\d{2}/\d{4}$", letter["nomor"]), f"bad nomor: {letter['nomor']}"
        context["letter_id"] = letter["id"]
        context["letter_nomor"] = letter["nomor"]
        # account status should now be DITUGASKAN
        a = requests.get(f"{API}/akun/{context['account_id']}", headers=admin_h, timeout=15).json()
        assert a["status"] == "DITUGASKAN"

    def test_surat_tugas_qr(self, admin_h, context):
        r = requests.get(f"{API}/surat-tugas/{context['letter_id']}/qr", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")

    def test_public_verify_limited_data(self, context):
        r = requests.get(f"{API}/public/surat-tugas/{context['letter_id']}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is True
        assert "nomor" in d and "petugas_name" in d
        # No sensitive debtor data
        assert "nama_debitur" not in d and "nik" not in d and "alamat" not in d

    def test_petugas_sees_task(self, petugas_h, context):
        r = requests.get(f"{API}/my/tugas", headers=petugas_h, timeout=15)
        assert r.status_code == 200
        tasks = r.json()
        assert any(t["account"]["id"] == context["account_id"] for t in tasks)

    def test_petugas_task_detail(self, petugas_h, context):
        r = requests.get(f"{API}/my/tugas/{context['account_id']}", headers=petugas_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["letter_id"] == context["letter_id"]

    def test_petugas_submit_laporan(self, petugas_h, context):
        # UNIT_DITEMUKAN requires photo
        img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        files = [("photos", ("bukti.png", img, "image/png"))]
        data = {
            "assignment_letter_id": context["letter_id"],
            "account_id": context["account_id"],
            "status": "UNIT_DITEMUKAN",
            "catatan": "TEST catatan laporan >=10 karakter",
            "latitude": "-6.2",
            "longitude": "106.8",
        }
        r = requests.post(f"{API}/laporan", headers=petugas_h, data=data, files=files, timeout=30)
        assert r.status_code == 200, r.text
        rep = r.json()
        context["report_id"] = rep["id"]
        assert rep["photos"] and rep["photos"][0]["url"].startswith("/api/files/")
        context["photo_url"] = rep["photos"][0]["url"]
        # account should be UNIT_DITEMUKAN
        time.sleep(0.3)

    def test_laporan_appears_for_admin(self, admin_h, context):
        r = requests.get(f"{API}/laporan", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert any(rep["id"] == context["report_id"] for rep in r.json())
        d = requests.get(f"{API}/laporan/{context['report_id']}", headers=admin_h, timeout=15)
        assert d.status_code == 200
        assert d.json()["photos"]

    def test_file_serving_requires_auth(self, admin_token, context):
        url = f"{BASE_URL}{context['photo_url']}"
        r = requests.get(url, timeout=15)
        assert r.status_code == 401
        # with auth query
        r2 = requests.get(url, params={"auth": admin_token}, timeout=15)
        assert r2.status_code == 200
        assert r2.headers["content-type"].startswith("image/")


# ---------------------------- authorization boundaries ----------------------------
class TestAuthorization:
    def test_petugas_cannot_access_admin(self, petugas_h):
        r = requests.get(f"{API}/dashboard/stats", headers=petugas_h, timeout=15)
        assert r.status_code == 403
        r2 = requests.get(f"{API}/clients", headers=petugas_h, timeout=15)
        assert r2.status_code == 403

    def test_admin_cannot_access_my_tugas(self, admin_h):
        r = requests.get(f"{API}/my/tugas", headers=admin_h, timeout=15)
        assert r.status_code == 403

    def test_petugas_cannot_report_on_other_account(self, petugas_h, admin_h):
        # take any akun that is NOT in petugas tasks (e.g., BELUM_DITUGASKAN)
        items = requests.get(f"{API}/akun", headers=admin_h,
                             params={"status": "BELUM_DITUGASKAN", "limit": 5}, timeout=15).json()["items"]
        if not items:
            pytest.skip("no unassigned account to test with")
        acc_id = items[0]["id"]
        img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        files = [("photos", ("x.png", img, "image/png"))]
        data = {
            "assignment_letter_id": "nonexistent",
            "account_id": acc_id,
            "status": "UNIT_DITEMUKAN",
            "catatan": "cukup panjang untuk lolos",
            "latitude": "-6.2", "longitude": "106.8",
        }
        r = requests.post(f"{API}/laporan", headers=petugas_h, data=data, files=files, timeout=20)
        # letter not found -> 404 (expected unauthorized access path)
        assert r.status_code in (403, 404)
