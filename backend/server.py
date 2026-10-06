from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Form, File, UploadFile, Query, Header
from fastapi.responses import StreamingResponse, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid
import io
import jwt
import bcrypt
import qrcode
from storage import put_object, get_object, init_storage, APP_NAME

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
APP_BASE_URL = os.environ.get('APP_BASE_URL', '')

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB

app = FastAPI(title="FieldCollector API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fieldcollector")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    return str(uuid.uuid4())

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def clean(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc = dict(doc)
        doc.pop("_id", None)
    return doc

async def next_sequence(name: str) -> int:
    res = await db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True,
    )
    return res["seq"]

async def log_audit(user: dict, activity: str, entity: str, entity_id: str, request: Request = None):
    ip = None
    if request is not None:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    await db.audit_logs.insert_one({
        "id": new_id(),
        "company_id": user.get("company_id"),
        "user_id": user.get("id"),
        "user_name": user.get("name"),
        "activity": activity,
        "entity": entity,
        "entity_id": entity_id,
        "ip_address": ip,
        "timestamp": now_iso(),
    })

# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------
async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    if user.get("status") == "nonaktif":
        raise HTTPException(status_code=403, detail="Akun Anda tidak aktif")
    return user

async def admin_required(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Anda tidak memiliki izin mengakses data ini")
    return user

async def petugas_required(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "petugas":
        raise HTTPException(status_code=403, detail="Khusus akun petugas")
    return user

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class LoginInput(BaseModel):
    email: EmailStr
    password: str

class ClientInput(BaseModel):
    nama_perusahaan: str
    alamat: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    nama_pic: Optional[str] = ""
    nomor_pic: Optional[str] = ""
    status: str = "aktif"

class SuratKuasaInput(BaseModel):
    nomor: str
    client_id: str
    tanggal_surat: Optional[str] = None
    tanggal_berlaku: Optional[str] = None
    tanggal_berakhir: Optional[str] = None
    file_url: Optional[str] = ""
    keterangan: Optional[str] = ""
    status: str = "aktif"

class AccountInput(BaseModel):
    nomor_kontrak: str
    nama_debitur: str
    nik: Optional[str] = ""
    telepon: Optional[str] = ""
    alamat: Optional[str] = ""
    provinsi: Optional[str] = ""
    kabupaten: Optional[str] = ""
    kecamatan: Optional[str] = ""
    kelurahan: Optional[str] = ""
    nomor_polisi: Optional[str] = ""
    jenis_kendaraan: Optional[str] = ""
    merk: Optional[str] = ""
    model: Optional[str] = ""
    tahun: Optional[str] = ""
    warna: Optional[str] = ""
    nomor_rangka: Optional[str] = ""
    nomor_mesin: Optional[str] = ""
    stnk_name: Optional[str] = ""
    client_id: str
    surat_kuasa_id: str
    keterangan: Optional[str] = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class PetugasInput(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    telepon: Optional[str] = ""
    tim: Optional[str] = ""
    status: str = "aktif"
    nik: Optional[str] = ""
    jabatan: Optional[str] = "PROFCOLL"
    no_sertifikasi: Optional[str] = ""
    sertifikasi_valid_until: Optional[str] = ""

class CompanyInput(BaseModel):
    nama: str
    alamat: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    city: Optional[str] = ""
    director_name: Optional[str] = ""
    director_position: Optional[str] = "DIREKTUR"
    company_code: Optional[str] = ""
    number_format: Optional[str] = "{sequence}/{company_code}/{month_name}/{year}"
    logo: Optional[str] = ""

class PenugasanInput(BaseModel):
    petugas_id: str
    account_ids: List[str]
    tanggal_tugas: Optional[str] = None
    masa_berlaku: Optional[str] = None
    catatan: Optional[str] = ""

class StatusUpdate(BaseModel):
    status: str

class ReviewInput(BaseModel):
    catatan_admin: Optional[str] = ""

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(data: LoginInput, request: Request):
    email = data.email.lower().strip()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    ident = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if user.get("status") == "nonaktif":
        raise HTTPException(status_code=403, detail="Akun Anda tidak aktif")
    await db.login_attempts.delete_one({"identifier": ident})
    token = create_access_token(user["id"], user["role"])
    safe = clean(user)
    safe.pop("password_hash", None)
    await log_audit(user, "Login", "user", user["id"], request)
    return {"token": token, "user": safe}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"ok": True}

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(admin_required)):
    cid = user["company_id"]
    base = {"company_id": cid}
    sk_aktif = await db.power_of_attorneys.count_documents({**base, "status": "aktif"})
    total_akun = await db.accounts.count_documents(base)
    tugas_aktif = await db.assignment_letters.count_documents({**base, "status": "aktif"})
    ditemukan = await db.accounts.count_documents({**base, "status": "UNIT_DITEMUKAN"})
    tidak_ditemukan = await db.accounts.count_documents({**base, "status": "TIDAK_DITEMUKAN"})
    belum_dikerjakan = await db.accounts.count_documents({**base, "status": "DITUGASKAN"})
    today_d = datetime.now(timezone.utc).date()
    today = today_d.isoformat()
    tomorrow = (today_d + timedelta(days=1)).isoformat()
    laporan_hari_ini = await db.field_reports.count_documents({**base, "created_at": {"$gte": today, "$lt": tomorrow}})
    return {
        "surat_kuasa_aktif": sk_aktif,
        "total_akun": total_akun,
        "tugas_aktif": tugas_aktif,
        "unit_ditemukan": ditemukan,
        "unit_tidak_ditemukan": tidak_ditemukan,
        "belum_dikerjakan": belum_dikerjakan,
        "laporan_hari_ini": laporan_hari_ini,
    }

@api_router.get("/dashboard/recent-activity")
async def recent_activity(user: dict = Depends(admin_required)):
    cid = user["company_id"]
    reports = await db.field_reports.find({"company_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(10)
    result = []
    for r in reports:
        acc = await db.accounts.find_one({"id": r["account_id"]}, {"_id": 0})
        letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"]}, {"_id": 0})
        petugas = await db.users.find_one({"id": r["petugas_id"]}, {"_id": 0, "password_hash": 0})
        result.append({
            "id": r["id"],
            "waktu": r["created_at"],
            "petugas": petugas["name"] if petugas else "-",
            "nomor_surat_tugas": letter["nomor"] if letter else "-",
            "nama_debitur": acc["nama_debitur"] if acc else "-",
            "status": r["status"],
        })
    return result

@api_router.get("/dashboard/reports-7days")
async def reports_7days(user: dict = Depends(admin_required)):
    cid = user["company_id"]
    out = []
    for i in range(6, -1, -1):
        day = (datetime.now(timezone.utc).date() - timedelta(days=i))
        start = day.isoformat()
        end = (day + timedelta(days=1)).isoformat()
        count = await db.field_reports.count_documents({"company_id": cid, "created_at": {"$gte": start, "$lt": end}})
        out.append({"date": start, "label": day.strftime("%d/%m"), "count": count})
    return out

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
@api_router.get("/clients")
async def list_clients(user: dict = Depends(admin_required), search: Optional[str] = None):
    q = {"company_id": user["company_id"]}
    if search:
        q["nama_perusahaan"] = {"$regex": search, "$options": "i"}
    items = await db.clients.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items

@api_router.post("/clients")
async def create_client(data: ClientInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc.update({"id": new_id(), "company_id": user["company_id"], "created_at": now_iso(), "updated_at": now_iso()})
    await db.clients.insert_one(doc)
    await log_audit(user, "Membuat klien", "client", doc["id"], request)
    return clean(doc)

@api_router.get("/clients/{client_id}")
async def get_client(client_id: str, user: dict = Depends(admin_required)):
    c = await db.clients.find_one({"id": client_id, "company_id": user["company_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    return c

@api_router.put("/clients/{client_id}")
async def update_client(client_id: str, data: ClientInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc["updated_at"] = now_iso()
    res = await db.clients.update_one({"id": client_id, "company_id": user["company_id"]}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    await log_audit(user, "Mengubah klien", "client", client_id, request)
    return await db.clients.find_one({"id": client_id}, {"_id": 0})

@api_router.patch("/clients/{client_id}/deactivate")
async def deactivate_client(client_id: str, request: Request, user: dict = Depends(admin_required)):
    await db.clients.update_one({"id": client_id, "company_id": user["company_id"]}, {"$set": {"status": "nonaktif", "updated_at": now_iso()}})
    await log_audit(user, "Menonaktifkan klien", "client", client_id, request)
    return {"ok": True}

# ---------------------------------------------------------------------------
# Surat Kuasa
# ---------------------------------------------------------------------------
async def enrich_sk(sk: dict) -> dict:
    client_doc = await db.clients.find_one({"id": sk["client_id"]}, {"_id": 0})
    sk["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    sk["total_akun"] = await db.accounts.count_documents({"surat_kuasa_id": sk["id"]})
    return sk

@api_router.get("/surat-kuasa")
async def list_sk(user: dict = Depends(admin_required), search: Optional[str] = None):
    q = {"company_id": user["company_id"]}
    if search:
        q["nomor"] = {"$regex": search, "$options": "i"}
    items = await db.power_of_attorneys.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [await enrich_sk(i) for i in items]

@api_router.post("/surat-kuasa")
async def create_sk(data: SuratKuasaInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc.update({"id": new_id(), "company_id": user["company_id"], "created_at": now_iso(), "updated_at": now_iso()})
    await db.power_of_attorneys.insert_one(doc)
    await log_audit(user, "Membuat Surat Kuasa", "surat_kuasa", doc["id"], request)
    return await enrich_sk(clean(doc))

@api_router.get("/surat-kuasa/{sk_id}")
async def get_sk(sk_id: str, user: dict = Depends(admin_required)):
    sk = await db.power_of_attorneys.find_one({"id": sk_id, "company_id": user["company_id"]}, {"_id": 0})
    if not sk:
        raise HTTPException(status_code=404, detail="Surat Kuasa tidak ditemukan")
    sk = await enrich_sk(sk)
    sk["accounts"] = await db.accounts.find({"surat_kuasa_id": sk_id}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return sk

@api_router.put("/surat-kuasa/{sk_id}")
async def update_sk(sk_id: str, data: SuratKuasaInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc["updated_at"] = now_iso()
    res = await db.power_of_attorneys.update_one({"id": sk_id, "company_id": user["company_id"]}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Surat Kuasa tidak ditemukan")
    await log_audit(user, "Mengubah Surat Kuasa", "surat_kuasa", sk_id, request)
    sk = await db.power_of_attorneys.find_one({"id": sk_id}, {"_id": 0})
    return await enrich_sk(sk)

# ---------------------------------------------------------------------------
# Accounts / Unit
# ---------------------------------------------------------------------------
async def enrich_account(acc: dict) -> dict:
    client_doc = await db.clients.find_one({"id": acc["client_id"]}, {"_id": 0})
    sk = await db.power_of_attorneys.find_one({"id": acc["surat_kuasa_id"]}, {"_id": 0})
    acc["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    acc["surat_kuasa_nomor"] = sk["nomor"] if sk else "-"
    return acc

@api_router.get("/akun")
async def list_accounts(
    user: dict = Depends(admin_required),
    search: Optional[str] = None, client_id: Optional[str] = None,
    status: Optional[str] = None, provinsi: Optional[str] = None,
    surat_kuasa_id: Optional[str] = None, page: int = 1, limit: int = 10,
):
    q = {"company_id": user["company_id"]}
    if client_id:
        q["client_id"] = client_id
    if status:
        q["status"] = status
    if provinsi:
        q["provinsi"] = {"$regex": provinsi, "$options": "i"}
    if surat_kuasa_id:
        q["surat_kuasa_id"] = surat_kuasa_id
    if search:
        q["$or"] = [
            {"nama_debitur": {"$regex": search, "$options": "i"}},
            {"nomor_kontrak": {"$regex": search, "$options": "i"}},
            {"nomor_polisi": {"$regex": search, "$options": "i"}},
        ]
    total = await db.accounts.count_documents(q)
    skip = (page - 1) * limit
    items = await db.accounts.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    items = [await enrich_account(i) for i in items]
    return {"items": items, "total": total, "page": page, "limit": limit}

@api_router.post("/akun")
async def create_account(data: AccountInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc.update({
        "id": new_id(), "company_id": user["company_id"], "status": "BELUM_DITUGASKAN",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    await db.accounts.insert_one(doc)
    await log_audit(user, "Membuat akun/unit", "account", doc["id"], request)
    return await enrich_account(clean(doc))

@api_router.get("/akun/{acc_id}")
async def get_account(acc_id: str, user: dict = Depends(admin_required)):
    acc = await db.accounts.find_one({"id": acc_id, "company_id": user["company_id"]}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return await enrich_account(acc)

@api_router.put("/akun/{acc_id}")
async def update_account(acc_id: str, data: AccountInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc["updated_at"] = now_iso()
    res = await db.accounts.update_one({"id": acc_id, "company_id": user["company_id"]}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    await log_audit(user, "Mengubah akun/unit", "account", acc_id, request)
    acc = await db.accounts.find_one({"id": acc_id}, {"_id": 0})
    return await enrich_account(acc)

# ---------------------------------------------------------------------------
# Petugas (users)
# ---------------------------------------------------------------------------
@api_router.get("/petugas")
async def list_petugas(user: dict = Depends(admin_required)):
    items = await db.users.find({"company_id": user["company_id"], "role": "petugas"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    for p in items:
        p["total_tugas"] = await db.assignment_letters.count_documents({"petugas_id": p["id"], "status": "aktif"})
    return items

@api_router.post("/petugas")
async def create_petugas(data: PetugasInput, request: Request, user: dict = Depends(admin_required)):
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah digunakan")
    seq = await next_sequence(f"petugas_{user['company_id']}")
    doc = {
        "id": new_id(), "company_id": user["company_id"], "role": "petugas",
        "name": data.name, "email": email,
        "password_hash": hash_password(data.password or "petugas123"),
        "telepon": data.telepon, "tim": data.tim, "status": data.status,
        "petugas_code": f"PTG-{seq:05d}",
        "nik": data.nik, "jabatan": data.jabatan,
        "no_sertifikasi": data.no_sertifikasi, "sertifikasi_valid_until": data.sertifikasi_valid_until,
        "avatar": "", "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await log_audit(user, "Membuat petugas", "user", doc["id"], request)
    out = clean(doc); out.pop("password_hash", None)
    return out

@api_router.get("/petugas/{pid}")
async def get_petugas(pid: str, user: dict = Depends(admin_required)):
    p = await db.users.find_one({"id": pid, "company_id": user["company_id"], "role": "petugas"}, {"_id": 0, "password_hash": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan")
    return p

@api_router.put("/petugas/{pid}")
async def update_petugas(pid: str, data: PetugasInput, request: Request, user: dict = Depends(admin_required)):
    upd = {"name": data.name, "email": data.email.lower().strip(), "telepon": data.telepon, "tim": data.tim, "status": data.status,
           "nik": data.nik, "jabatan": data.jabatan, "no_sertifikasi": data.no_sertifikasi,
           "sertifikasi_valid_until": data.sertifikasi_valid_until, "updated_at": now_iso()}
    if data.password:
        upd["password_hash"] = hash_password(data.password)
    res = await db.users.update_one({"id": pid, "company_id": user["company_id"], "role": "petugas"}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan")
    await log_audit(user, "Mengubah petugas", "user", pid, request)
    return await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0})

# ---------------------------------------------------------------------------
# Penugasan -> Surat Tugas
# ---------------------------------------------------------------------------
async def enrich_letter(letter: dict) -> dict:
    petugas = await db.users.find_one({"id": letter["petugas_id"]}, {"_id": 0, "password_hash": 0})
    client_doc = await db.clients.find_one({"id": letter.get("client_id")}, {"_id": 0})
    sk = await db.power_of_attorneys.find_one({"id": letter.get("surat_kuasa_id")}, {"_id": 0})
    letter["petugas_name"] = petugas["name"] if petugas else "-"
    letter["petugas_code"] = petugas["petugas_code"] if petugas else "-"
    letter["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    letter["surat_kuasa_nomor"] = sk["nomor"] if sk else "-"
    accs = await db.accounts.find({"id": {"$in": letter.get("account_ids", [])}}, {"_id": 0}).to_list(1000)
    letter["accounts"] = accs
    return letter

@api_router.post("/penugasan")
async def create_penugasan(data: PenugasanInput, request: Request, user: dict = Depends(admin_required)):
    if not data.account_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu akun/unit")
    petugas = await db.users.find_one({"id": data.petugas_id, "company_id": user["company_id"], "role": "petugas"})
    if not petugas:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan")
    accs = await db.accounts.find({"id": {"$in": data.account_ids}, "company_id": user["company_id"]}, {"_id": 0}).to_list(1000)
    if len(accs) != len(data.account_ids):
        raise HTTPException(status_code=400, detail="Sebagian akun tidak ditemukan")
    for a in accs:
        if a["status"] not in ("BELUM_DITUGASKAN",):
            raise HTTPException(status_code=400, detail=f"Akun {a['nama_debitur']} sudah ditugaskan")
    # business rule: surat kuasa harus aktif
    sk_id = accs[0]["surat_kuasa_id"]
    sk = await db.power_of_attorneys.find_one({"id": sk_id})
    if not sk or sk.get("status") != "aktif":
        raise HTTPException(status_code=400, detail="Surat Kuasa tidak aktif, tidak dapat membuat Surat Tugas")
    client_id = accs[0]["client_id"]

    now = datetime.now(timezone.utc)
    seq = await next_sequence(f"st_{user['company_id']}_{now.year}_{now.month}")
    nomor = f"ST/FC/{now.year}/{now.month:02d}/{seq:04d}"

    assignment_id = new_id()
    letter_id = new_id()
    await db.assignments.insert_one({
        "id": assignment_id, "company_id": user["company_id"], "petugas_id": data.petugas_id,
        "tanggal_tugas": data.tanggal_tugas, "masa_berlaku": data.masa_berlaku,
        "catatan": data.catatan, "assignment_letter_id": letter_id,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    for aid in data.account_ids:
        await db.assignment_accounts.insert_one({
            "id": new_id(), "assignment_id": assignment_id, "letter_id": letter_id, "account_id": aid,
        })
    letter = {
        "id": letter_id, "company_id": user["company_id"], "nomor": nomor,
        "assignment_id": assignment_id, "petugas_id": data.petugas_id,
        "client_id": client_id, "surat_kuasa_id": sk_id,
        "account_ids": data.account_ids, "tanggal": data.tanggal_tugas or now_iso(),
        "masa_berlaku": data.masa_berlaku, "catatan": data.catatan, "status": "aktif",
        "document_status": "DRAFT", "template_version": "v1",
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.assignment_letters.insert_one(letter)
    await db.accounts.update_many({"id": {"$in": data.account_ids}}, {"$set": {"status": "DITUGASKAN", "updated_at": now_iso()}})
    await log_audit(user, "Membuat penugasan", "assignment", assignment_id, request)
    await log_audit(user, "Membuat Surat Tugas", "assignment_letter", letter_id, request)
    return await enrich_letter(clean(letter))

@api_router.get("/surat-tugas")
async def list_surat_tugas(user: dict = Depends(admin_required), search: Optional[str] = None, petugas_id: Optional[str] = None, status: Optional[str] = None):
    q = {"company_id": user["company_id"]}
    if search:
        q["nomor"] = {"$regex": search, "$options": "i"}
    if petugas_id:
        q["petugas_id"] = petugas_id
    if status:
        q["status"] = status
    items = await db.assignment_letters.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [await enrich_letter(i) for i in items]

@api_router.get("/surat-tugas/{lid}")
async def get_surat_tugas(lid: str, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]}, {"_id": 0})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    return await enrich_letter(letter)

@api_router.patch("/surat-tugas/{lid}/status")
async def update_st_status(lid: str, data: StatusUpdate, request: Request, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    await db.assignment_letters.update_one({"id": lid}, {"$set": {"status": data.status, "updated_at": now_iso()}})
    if data.status in ("dibatalkan", "kedaluwarsa"):
        await db.accounts.update_many(
            {"id": {"$in": letter.get("account_ids", [])}, "status": "DITUGASKAN"},
            {"$set": {"status": "BELUM_DITUGASKAN", "updated_at": now_iso()}},
        )
    await log_audit(user, f"Mengubah status Surat Tugas: {data.status}", "assignment_letter", lid, request)
    letter = await db.assignment_letters.find_one({"id": lid}, {"_id": 0})
    return await enrich_letter(letter)

@api_router.get("/surat-tugas/{lid}/qr")
async def surat_tugas_qr(lid: str):
    letter = await db.assignment_letters.find_one({"id": lid}, {"_id": 0})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    code = letter.get("generate_code")
    verify_url = f"{APP_BASE_URL}/verify/surat-tugas/{code}" if code else f"{APP_BASE_URL}/verifikasi/{lid}"
    img = qrcode.make(verify_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

# ---------------------------------------------------------------------------
# Public verification
# ---------------------------------------------------------------------------
@api_router.get("/public/surat-tugas/{lid}")
async def public_verify(lid: str):
    letter = await db.assignment_letters.find_one({"id": lid}, {"_id": 0})
    if not letter:
        return {"valid": False, "message": "Surat Tugas tidak ditemukan"}
    petugas = await db.users.find_one({"id": letter["petugas_id"]}, {"_id": 0, "password_hash": 0})
    company = await db.companies.find_one({"id": letter["company_id"]}, {"_id": 0})
    valid = letter["status"] == "aktif"
    return {
        "valid": valid,
        "nomor": letter["nomor"],
        "petugas_name": petugas["name"] if petugas else "-",
        "company_name": company["nama"] if company else "-",
        "tanggal_berlaku": letter.get("masa_berlaku") or letter.get("tanggal"),
        "status": letter["status"],
    }

# ---------------------------------------------------------------------------
# Surat Penugasan + BASTK document system (dynamic template, snapshot, verify)
# ---------------------------------------------------------------------------
ID_MONTHS_UP = ["", "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI", "JULI",
                "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER"]
MONTH_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def int_to_roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    res = ""
    for v, s in vals:
        while n >= v:
            res += s
            n -= v
    return res


def _date_only(iso):
    return iso[:10] if iso else ""


async def build_document_data(letter: dict, generated_by_name: str = "") -> dict:
    company = await db.companies.find_one({"id": letter["company_id"]}, {"_id": 0}) or {}
    officer = await db.users.find_one({"id": letter["petugas_id"]}, {"_id": 0, "password_hash": 0}) or {}
    client_doc = await db.clients.find_one({"id": letter.get("client_id")}, {"_id": 0}) or {}
    accs = await db.accounts.find({"id": {"$in": letter.get("account_ids", [])}}, {"_id": 0}).to_list(1000)
    acc_list = [{
        "contract_number": a.get("nomor_kontrak", ""),
        "debtor_name": a.get("nama_debitur", ""),
        "debtor_address": a.get("alamat", ""),
        "debtor_phone": a.get("telepon", ""),
        "debtor_nik": a.get("nik", ""),
        "brand": ((a.get("merk", "") + " " + a.get("model", "")).strip()) or a.get("jenis_kendaraan", ""),
        "jenis": a.get("jenis_kendaraan", ""),
        "model": a.get("model", ""),
        "year": a.get("tahun", ""),
        "color": a.get("warna", ""),
        "license_plate": a.get("nomor_polisi", ""),
        "chassis_number": a.get("nomor_rangka", ""),
        "engine_number": a.get("nomor_mesin", ""),
        "stnk_name": a.get("stnk_name", "") or a.get("nama_debitur", ""),
    } for a in accs]
    return {
        "company": {
            "name": company.get("nama", ""), "city": company.get("city", ""),
            "address": company.get("alamat", ""), "phone": company.get("telepon", ""),
            "director_name": company.get("director_name", ""),
            "director_position": company.get("director_position", "DIREKTUR"),
            "company_code": company.get("company_code", ""), "logo": company.get("logo", ""),
        },
        "finance": {"name": client_doc.get("nama_perusahaan", "")},
        "officer": {
            "name": officer.get("name", ""), "nik": officer.get("nik", ""),
            "position": officer.get("jabatan", "PROFCOLL"), "code": officer.get("petugas_code", ""),
            "certification_number": officer.get("no_sertifikasi", ""),
            "certification_valid_until": officer.get("sertifikasi_valid_until", ""),
            "phone": officer.get("telepon", ""),
        },
        "letter": {
            "document_number": letter.get("document_number", ""),
            "generate_code": letter.get("generate_code", ""),
            "register_number": letter.get("register_number", ""),
            "issue_date": letter.get("issue_date") or _date_only(letter.get("tanggal")),
            "valid_from": _date_only(letter.get("tanggal")),
            "valid_until": _date_only(letter.get("masa_berlaku")),
            "status": letter.get("status", ""),
        },
        "accounts": acc_list,
        "generated_by": generated_by_name or letter.get("generated_by", ""),
        "generated_at": letter.get("generated_at") or now_iso(),
    }


async def get_document_payload(letter: dict) -> dict:
    template = await db.document_templates.find_one(
        {"company_id": letter["company_id"], "version": letter.get("template_version", "v1")}, {"_id": 0})
    if not template:
        template = await db.document_templates.find_one({"version": "v1"}, {"_id": 0})
    if letter.get("document_status") == "ACTIVE" and letter.get("document_snapshot"):
        data = letter["document_snapshot"]
    else:
        data = await build_document_data(letter)
    return {
        "document_status": letter.get("document_status", "DRAFT"),
        "is_finalized": letter.get("document_status") == "ACTIVE",
        "template": template, "data": data,
        "letter_id": letter["id"], "st_nomor": letter.get("nomor"),
        "letter_status": letter.get("status"),
    }


@api_router.get("/surat-tugas/{lid}/document")
async def get_document(lid: str, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]}, {"_id": 0})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    return await get_document_payload(letter)


@api_router.post("/surat-tugas/{lid}/finalize")
async def finalize_document(lid: str, request: Request, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    if letter.get("document_status") == "ACTIVE":
        letter.pop("_id", None)
        return await get_document_payload(letter)
    if letter.get("status") != "aktif":
        raise HTTPException(status_code=400, detail="Surat Tugas tidak aktif, tidak dapat difinalisasi")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    now = datetime.now(timezone.utc)
    year = now.year
    seq = await next_sequence(f"docnum_{user['company_id']}_{year}")
    fmt = company.get("number_format") or "{sequence}/{company_code}/{month_name}/{year}"
    try:
        document_number = fmt.format(sequence=f"{seq:04d}", company_code=company.get("company_code", ""),
                                     month_name=ID_MONTHS_UP[now.month], year=year)
    except (KeyError, IndexError, ValueError):
        document_number = f"{seq:04d}/{company.get('company_code', '')}/{ID_MONTHS_UP[now.month]}/{year}"
    generate_code = f"GNR-{year}-{uuid.uuid4().hex[:20].upper()}"
    reg_seq = await next_sequence(f"bastk_{user['company_id']}_{year}")
    register_number = f"{reg_seq}/{int_to_roman(year)}/{MONTH_ROMAN[now.month]}"
    upd = {
        "document_number": document_number, "generate_code": generate_code,
        "register_number": register_number, "issue_date": now.date().isoformat(),
        "document_status": "ACTIVE", "template_version": "v1",
        "generated_by": user["name"], "generated_at": now_iso(), "updated_at": now_iso(),
    }
    letter.update(upd)
    snapshot = await build_document_data(letter, user["name"])
    upd["document_snapshot"] = snapshot
    await db.assignment_letters.update_one({"id": lid}, {"$set": upd})
    await log_audit(user, "Finalisasi Surat Penugasan", "assignment_letter", lid, request)
    letter = await db.assignment_letters.find_one({"id": lid}, {"_id": 0})
    return await get_document_payload(letter)


@api_router.get("/public/verify/{code}")
async def public_verify_code(code: str):
    letter = await db.assignment_letters.find_one({"generate_code": code}, {"_id": 0})
    if not letter:
        return {"valid": False, "doc_status": "TIDAK DITEMUKAN", "message": "Dokumen tidak ditemukan"}
    company = await db.companies.find_one({"id": letter["company_id"]}, {"_id": 0}) or {}
    officer = await db.users.find_one({"id": letter["petugas_id"]}, {"_id": 0, "password_hash": 0}) or {}
    st = letter.get("status")
    status_map = {"aktif": "VALID", "selesai": "VALID", "dibatalkan": "DIBATALKAN", "kedaluwarsa": "KEDALUWARSA"}
    return {
        "valid": st in ("aktif", "selesai"),
        "doc_status": status_map.get(st, "TIDAK VALID"),
        "nomor": letter.get("document_number") or letter.get("nomor"),
        "company_name": company.get("nama", ""),
        "petugas_name": officer.get("name", ""),
        "issued_at": letter.get("generated_at"),
        "valid_until": _date_only(letter.get("masa_berlaku")),
        "generate_code": code,
    }


@api_router.put("/company")
async def update_company(data: CompanyInput, request: Request, user: dict = Depends(admin_required)):
    await db.companies.update_one({"id": user["company_id"]}, {"$set": {**data.model_dump(), "updated_at": now_iso()}})
    await log_audit(user, "Mengubah profil perusahaan", "company", user["company_id"], request)
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})


# ---------------------------------------------------------------------------
# Petugas (field officer) views
# ---------------------------------------------------------------------------
@api_router.get("/my/tugas")
async def my_tugas(user: dict = Depends(petugas_required)):
    letters = await db.assignment_letters.find({"petugas_id": user["id"], "status": "aktif"}, {"_id": 0}).to_list(500)
    result = []
    for letter in letters:
        sk = await db.power_of_attorneys.find_one({"id": letter["surat_kuasa_id"]}, {"_id": 0})
        client_doc = await db.clients.find_one({"id": letter["client_id"]}, {"_id": 0})
        for acc in await db.accounts.find({"id": {"$in": letter["account_ids"]}}, {"_id": 0}).to_list(1000):
            rep = await db.field_reports.find_one({"account_id": acc["id"], "assignment_letter_id": letter["id"]}, {"_id": 0})
            result.append({
                "account": acc,
                "letter_nomor": letter["nomor"],
                "letter_id": letter["id"],
                "surat_kuasa_nomor": sk["nomor"] if sk else "-",
                "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
                "catatan_admin": letter.get("catatan", ""),
                "sudah_dilaporkan": rep is not None,
            })
    return result

@api_router.get("/my/tugas/{account_id}")
async def my_tugas_detail(account_id: str, user: dict = Depends(petugas_required)):
    letter = await db.assignment_letters.find_one({"petugas_id": user["id"], "account_ids": account_id, "status": "aktif"}, {"_id": 0})
    if not letter:
        raise HTTPException(status_code=404, detail="Tugas tidak ditemukan")
    acc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    sk = await db.power_of_attorneys.find_one({"id": letter["surat_kuasa_id"]}, {"_id": 0})
    client_doc = await db.clients.find_one({"id": letter["client_id"]}, {"_id": 0})
    rep = await db.field_reports.find_one({"account_id": account_id, "assignment_letter_id": letter["id"]}, {"_id": 0})
    await log_audit(user, "Membuka tugas", "account", account_id)
    return {
        "account": acc, "letter_nomor": letter["nomor"], "letter_id": letter["id"],
        "surat_kuasa_nomor": sk["nomor"] if sk else "-",
        "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
        "catatan_admin": letter.get("catatan", ""),
        "existing_report": rep,
    }

@api_router.get("/my/riwayat")
async def my_riwayat(user: dict = Depends(petugas_required), status: Optional[str] = None):
    q = {"petugas_id": user["id"]}
    if status:
        q["status"] = status
    reports = await db.field_reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in reports:
        acc = await db.accounts.find_one({"id": r["account_id"]}, {"_id": 0})
        letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"]}, {"_id": 0})
        r["nama_debitur"] = acc["nama_debitur"] if acc else "-"
        r["nomor_polisi"] = acc["nomor_polisi"] if acc else "-"
        r["letter_nomor"] = letter["nomor"] if letter else "-"
        r["photos"] = await db.report_photos.find({"report_id": r["id"]}, {"_id": 0}).to_list(10)
    return reports

@api_router.get("/my/profile")
async def my_profile(user: dict = Depends(petugas_required)):
    return user

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
ACCOUNT_STATUS_MAP = {
    "UNIT_DITEMUKAN": "UNIT_DITEMUKAN",
    "TIDAK_DITEMUKAN": "TIDAK_DITEMUKAN",
    "ALAMAT_TIDAK_SESUAI": "ALAMAT_TIDAK_SESUAI",
    "PINDAH_ALAMAT": "ALAMAT_TIDAK_SESUAI",
    "UNIT_TIDAK_ADA": "TIDAK_DITEMUKAN",
    "LAINNYA": "DALAM_PROSES",
}

@api_router.post("/laporan")
async def create_laporan(
    request: Request,
    assignment_letter_id: str = Form(...),
    account_id: str = Form(...),
    status: str = Form(...),
    catatan: str = Form(...),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    lokasi_alasan: Optional[str] = Form(None),
    photos: List[UploadFile] = File(default=[]),
    user: dict = Depends(petugas_required),
):
    letter = await db.assignment_letters.find_one({"id": assignment_letter_id, "petugas_id": user["id"]})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    if letter["status"] != "aktif":
        raise HTTPException(status_code=400, detail="Surat Tugas tidak aktif")
    if account_id not in letter.get("account_ids", []):
        raise HTTPException(status_code=403, detail="Akun ini bukan bagian dari tugas Anda")
    existing = await db.field_reports.find_one({"account_id": account_id, "assignment_letter_id": assignment_letter_id, "status": "SUBMITTED"})
    if existing:
        raise HTTPException(status_code=400, detail="Laporan untuk tugas ini sudah dikirim")
    if len(catatan.strip()) < 10:
        raise HTTPException(status_code=400, detail="Catatan petugas wajib minimal 10 karakter")
    photos = [p for p in photos if p and p.filename]
    if status == "UNIT_DITEMUKAN" and len(photos) < 1:
        raise HTTPException(status_code=400, detail="Foto bukti wajib minimal 1 untuk unit ditemukan")
    if len(photos) > 5:
        raise HTTPException(status_code=400, detail="Maksimal 5 foto")
    if (not latitude or not longitude) and not (lokasi_alasan and lokasi_alasan.strip()):
        raise HTTPException(status_code=400, detail="Lokasi GPS wajib, atau berikan alasan jika GPS ditolak")

    report_id = new_id()
    saved = []
    for p in photos:
        if p.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Format foto tidak diizinkan (hanya JPG/PNG/WEBP)")
        content = await p.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Ukuran foto maksimal 8MB")
        ext = (p.filename.rsplit(".", 1)[-1] if "." in p.filename else "jpg").lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        obj_path = f"{APP_NAME}/companies/{user['company_id']}/reports/{report_id}/{new_id()}.{ext}"
        result = put_object(obj_path, content, p.content_type or "image/jpeg")
        saved.append({"storage_path": result["path"], "url": f"/api/files/{result['path']}"})

    report = {
        "id": report_id, "company_id": user["company_id"], "petugas_id": user["id"],
        "assignment_letter_id": assignment_letter_id, "account_id": account_id,
        "status": status, "catatan": catatan,
        "latitude": float(latitude) if latitude else None,
        "longitude": float(longitude) if longitude else None,
        "lokasi_alasan": lokasi_alasan or "",
        "report_status": "SUBMITTED",
        "catatan_admin": "", "reviewed": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.field_reports.insert_one(report)
    for ph in saved:
        await db.report_photos.insert_one({"id": new_id(), "report_id": report_id, "url": ph["url"], "storage_path": ph["storage_path"], "created_at": now_iso()})
    await db.accounts.update_one({"id": account_id}, {"$set": {"status": ACCOUNT_STATUS_MAP.get(status, "DALAM_PROSES"), "updated_at": now_iso()}})
    await log_audit(user, f"Mengirim laporan ({status})", "field_report", report_id, request)
    out = clean(report)
    out["photos"] = [{"url": s["url"]} for s in saved]
    return out

@api_router.get("/laporan")
async def list_laporan(
    user: dict = Depends(admin_required),
    petugas_id: Optional[str] = None, client_id: Optional[str] = None,
    status: Optional[str] = None, tanggal: Optional[str] = None,
    provinsi: Optional[str] = None, search: Optional[str] = None,
):
    q = {"company_id": user["company_id"]}
    if petugas_id:
        q["petugas_id"] = petugas_id
    if status:
        q["status"] = status
    if tanggal:
        try:
            nextday = (datetime.fromisoformat(tanggal).date() + timedelta(days=1)).isoformat()
        except ValueError:
            nextday = tanggal + "T99"
        q["created_at"] = {"$gte": tanggal, "$lt": nextday}
    reports = await db.field_reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    result = []
    for r in reports:
        acc = await db.accounts.find_one({"id": r["account_id"]}, {"_id": 0})
        letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"]}, {"_id": 0})
        petugas = await db.users.find_one({"id": r["petugas_id"]}, {"_id": 0, "password_hash": 0})
        client_doc = await db.clients.find_one({"id": letter["client_id"]}, {"_id": 0}) if letter else None
        if client_id and (not letter or letter.get("client_id") != client_id):
            continue
        if provinsi and (not acc or provinsi.lower() not in (acc.get("provinsi", "").lower())):
            continue
        photos = await db.report_photos.find({"report_id": r["id"]}, {"_id": 0}).to_list(10)
        result.append({
            **r,
            "nama_debitur": acc["nama_debitur"] if acc else "-",
            "nomor_polisi": acc["nomor_polisi"] if acc else "-",
            "provinsi": acc.get("provinsi", "") if acc else "",
            "petugas_name": petugas["name"] if petugas else "-",
            "letter_nomor": letter["nomor"] if letter else "-",
            "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
            "photos": photos,
        })
    if search:
        s = search.lower()
        result = [r for r in result if s in r["nama_debitur"].lower() or s in r["nomor_polisi"].lower() or s in r["letter_nomor"].lower()]
    return result

@api_router.get("/laporan/{rid}")
async def get_laporan(rid: str, user: dict = Depends(admin_required)):
    r = await db.field_reports.find_one({"id": rid, "company_id": user["company_id"]}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
    acc = await db.accounts.find_one({"id": r["account_id"]}, {"_id": 0})
    letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"]}, {"_id": 0})
    petugas = await db.users.find_one({"id": r["petugas_id"]}, {"_id": 0, "password_hash": 0})
    client_doc = await db.clients.find_one({"id": letter["client_id"]}, {"_id": 0}) if letter else None
    photos = await db.report_photos.find({"report_id": rid}, {"_id": 0}).to_list(10)
    await log_audit(user, "Melihat laporan", "field_report", rid)
    return {
        **r, "account": acc, "petugas_name": petugas["name"] if petugas else "-",
        "letter_nomor": letter["nomor"] if letter else "-",
        "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
        "photos": photos,
    }

@api_router.patch("/laporan/{rid}/review")
async def review_laporan(rid: str, data: ReviewInput, request: Request, user: dict = Depends(admin_required)):
    res = await db.field_reports.update_one(
        {"id": rid, "company_id": user["company_id"]},
        {"$set": {"catatan_admin": data.catatan_admin, "reviewed": True, "report_status": "REVIEWED", "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Laporan tidak ditemukan")
    await log_audit(user, "Mereview laporan", "field_report", rid, request)
    return {"ok": True}

# ---------------------------------------------------------------------------
# Audit logs & settings
# ---------------------------------------------------------------------------
@api_router.get("/audit-logs")
async def list_audit(user: dict = Depends(admin_required)):
    return await db.audit_logs.find({"company_id": user["company_id"]}, {"_id": 0}).sort("timestamp", -1).to_list(100)

@api_router.get("/company")
async def get_company(user: dict = Depends(get_current_user)):
    c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return c

# ---------------------------------------------------------------------------
# File serving (object storage proxy). Supports query-param auth for <img>.
# ---------------------------------------------------------------------------
@api_router.get("/files/{path:path}")
async def serve_file(path: str, authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif auth:
        token = auth
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    record = await db.report_photos.find_one({"storage_path": path})
    if not record:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    data, content_type = get_object(path)
    return Response(content=data, media_type=content_type)

# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.accounts.create_index("company_id")
    await db.field_reports.create_index("petugas_id")
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    from seed import seed_all
    await seed_all(db)

@app.on_event("shutdown")
async def shutdown():
    client.close()
