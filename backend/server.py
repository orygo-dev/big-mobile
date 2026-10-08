from dotenv import load_dotenv
from pathlib import Path
import os
import asyncio
from contextlib import suppress

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Form, File, UploadFile, Query, Header
from fastapi.responses import StreamingResponse, Response, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Literal, Optional
from datetime import date, datetime, timezone, timedelta
import logging
import uuid
import io
import base64
import math
import re
import time
import hmac
import jwt
import bcrypt
import qrcode
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from requests.exceptions import RequestException
from PIL import Image, ImageOps, UnidentifiedImageError
from storage import put_object, get_object, delete_object, init_storage, StorageUnavailable, APP_NAME
from starlette.concurrency import run_in_threadpool
from pdf_validation import validate_pdf
import transactions
import security
import idempotency

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = transactions.Database(client[os.environ['DB_NAME']])
transactional = idempotency.decorator(lambda: db, lambda operation: transactions.run(client, operation))

JWT_SECRET = os.environ['JWT_SECRET']
security.validate_configuration()
JWT_ALGORITHM = "HS256"
APP_BASE_URL = os.environ.get('APP_BASE_URL', '')

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB


def verified_image_format(content, formats, max_pixels):
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in formats or image.width * image.height > max_pixels:
                raise ValueError("Invalid image format/resolution")
            image.verify()
            return image.format
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="File gambar tidak valid atau resolusinya terlalu besar")

app = FastAPI(title="BIG Mobile API", docs_url=None if security.PRODUCTION else "/docs", redoc_url=None if security.PRODUCTION else "/redoc", openapi_url=None if security.PRODUCTION else "/openapi.json")
app.state.database_ready = False
app.state.metrics = {"requests": 0, "server_errors": 0, "duration_ms": 0}
api_router = APIRouter(prefix="/api")

SERVICE_UNAVAILABLE = "Layanan aplikasi sedang dipulihkan. Silakan coba lagi dalam beberapa saat."


@app.middleware("http")
async def require_database_ready(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed = {value.strip() for value in os.environ.get("CORS_ORIGINS", "").split(",") if value.strip()}
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if origin and origin not in allowed:
            return JSONResponse(status_code=403, content={"detail": "Origin permintaan tidak diizinkan"})
        if security.PRODUCTION and request.cookies.get(security.COOKIE_NAME) and not request.headers.get("Authorization") and not origin:
            return JSONResponse(status_code=403, content={"detail": "Origin diperlukan untuk permintaan sesi browser"})
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > 45 * 1024 * 1024):
        return JSONResponse(status_code=413, content={"detail": "Ukuran permintaan terlalu besar"})
    if request.url.path.startswith("/api/") and request.url.path != "/api/health" and request.method != "OPTIONS" and not app.state.database_ready:
        return JSONResponse(status_code=503, content={"detail": SERVICE_UNAVAILABLE}, headers={"Retry-After": "15"})
    request_id = new_id()
    request.state.request_id = request_id
    started = time.monotonic()
    result = await call_next(request)
    result.headers["X-Request-ID"] = request_id
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        result.headers.setdefault("Cache-Control", "no-store")
    # Never log query strings, request bodies, email, tokens or raw object paths.
    route = getattr(request.scope.get("route"), "path", "unmatched")
    app.state.metrics["requests"] += 1
    app.state.metrics["server_errors"] += int(result.status_code >= 500)
    app.state.metrics["duration_ms"] += round((time.monotonic()-started)*1000)
    logger.info("request id=%s method=%s route=%s status=%s duration_ms=%s", request_id, request.method, route, result.status_code, round((time.monotonic()-started)*1000))
    return result


@app.exception_handler(ConnectionFailure)
async def database_connection_error(request: Request, exception: ConnectionFailure):
    app.state.database_ready = False
    logger.warning("Database connection unavailable: %s", type(exception).__name__)
    return JSONResponse(status_code=503, content={"detail": SERVICE_UNAVAILABLE}, headers={"Retry-After": "15"})


@api_router.get("/health")
async def service_health():
    ready = app.state.database_ready and (not security.PRODUCTION or getattr(app.state, "storage_ready", False))
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "unavailable", "database": "ready" if app.state.database_ready else "unavailable"})


@api_router.get("/metrics", include_in_schema=False)
async def service_metrics(request: Request):
    expected = os.environ.get("MONITOR_TOKEN", "")
    if not expected or not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + expected):
        raise HTTPException(status_code=404, detail="Tidak ditemukan")
    return {**app.state.metrics, "database_ready": app.state.database_ready, "storage_ready": getattr(app.state, "storage_ready", False), "transactions": transactions.ENABLED}


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exception: Exception):
    app.state.metrics["server_errors"] += 1
    identity = getattr(request.state, "request_id", new_id())
    logger.error("request id=%s failed exception=%s", identity, type(exception).__name__)
    return JSONResponse(status_code=500, content={"detail": "Terjadi gangguan pada server. Silakan coba lagi.", "request_id": identity}, headers={"X-Request-ID": identity})


@app.exception_handler(RequestException)
@app.exception_handler(StorageUnavailable)
async def storage_service_error(request: Request, exception: RequestException):
    logger.warning("Storage service unavailable: %s", type(exception).__name__)
    return JSONResponse(status_code=503, content={"detail": "Penyimpanan file belum dapat dihubungi. Silakan coba lagi dalam beberapa saat."})

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fieldcollector")
if security.PRODUCTION:
    for handler in logging.getLogger().handlers:
        handler.setFormatter(security.JsonFormatter())
    for name in ("uvicorn", "uvicorn.error"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(security.JsonFormatter())
    logging.getLogger("uvicorn.access").disabled = True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def paged_documents(collection, query, response, page, limit, projection=None):
    cursor = collection.find(query, projection or {"_id": 0}).sort([("created_at", -1), ("id", 1)])
    if page > 1:
        cursor = cursor.skip((page - 1) * limit)
    items = await cursor.to_list(limit)
    if response is not None:
        total = int(await collection.count_documents(query))
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Next-Page"] = str(page + 1) if page * limit < total else ""
    return items

def new_id() -> str:
    return str(uuid.uuid4())

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, role: str, token_version: int = 0) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=security.TOKEN_HOURS),
        "iat": datetime.now(timezone.utc), "jti": new_id(),
        "iss": security.ISSUER, "aud": security.AUDIENCE, "ver": token_version,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def clean(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc = dict(doc)
        doc.pop("_id", None)
    return doc

def validate_report_location(latitude, longitude, reason):
    if latitude in (None, "") and longitude in (None, ""):
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(status_code=400, detail="Berikan alasan GPS tidak tersedia (min 5 karakter)")
        return None, None
    try:
        lat, lng = float(latitude), float(longitude)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Koordinat GPS tidak valid")
    if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise HTTPException(status_code=400, detail="Koordinat GPS tidak valid")
    return lat, lng

def validate_assignment_dates(valid_from, valid_until):
    try:
        start = date.fromisoformat(valid_from) if valid_from else None
        end = date.fromisoformat(valid_until) if valid_until else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Tanggal penugasan tidak valid (YYYY-MM-DD)")
    if start and end and end < start:
        raise HTTPException(status_code=400, detail="Tanggal akhir tidak boleh sebelum tanggal mulai")
    return start, end

def letter_is_expired(letter):
    value = letter.get("masa_berlaku")
    if not value:
        return False
    try:
        return date.fromisoformat(value[:10]) < datetime.now(timezone(timedelta(hours=7))).date()
    except (ValueError, TypeError):
        return True

def task_availability(assignment, sk=None, client_doc=None):
    today = datetime.now(timezone(timedelta(hours=7))).date()
    start, end = validate_assignment_dates(assignment.get("valid_from"), assignment.get("valid_until"))
    reason = ""
    if assignment.get("status") != ASSIGNMENT_ACTIVE:
        reason = "Penugasan tidak aktif"
    elif start and start > today:
        reason = f"Penugasan baru dapat dikerjakan mulai {start.isoformat()}"
    elif end and end < today:
        reason = "Masa berlaku penugasan sudah berakhir"
    elif sk is not None:
        sk_start, sk_end = validate_assignment_dates(sk.get("tanggal_berlaku"), sk.get("tanggal_berakhir"))
        if sk.get("status") != "aktif" or (sk_start and sk_start > today) or (sk_end and sk_end < today):
            reason = "Surat Kuasa tidak aktif atau di luar masa berlaku"
    if client_doc and client_doc.get("status", "aktif") != "aktif":
        reason = "Klien sudah tidak aktif"
    return {"valid_from": assignment.get("valid_from"), "valid_until": assignment.get("valid_until"), "can_report": not reason, "blocked_reason": reason}

async def validate_client_reference(client_id: str, company_id: str):
    if not await db.clients.find_one({"id": client_id, "company_id": company_id}):
        raise HTTPException(status_code=400, detail="Klien tidak ditemukan di perusahaan Anda")
    if transactions.session_context.get() is not None:
        await db.clients.update_one({"id": client_id, "company_id": company_id}, {"$inc": {"relation_version": 1}})

async def validate_account_references(data, company_id: str):
    await validate_client_reference(data.client_id, company_id)
    sk = await db.power_of_attorneys.find_one({"id": data.surat_kuasa_id, "company_id": company_id, "client_id": data.client_id})
    if not sk:
        raise HTTPException(status_code=400, detail="Surat Kuasa tidak sesuai dengan klien atau perusahaan")
    if transactions.session_context.get() is not None:
        await db.power_of_attorneys.update_one({"id": data.surat_kuasa_id, "company_id": company_id}, {"$inc": {"relation_version": 1}})
    if data.debtor_id and not await db.debtors.find_one({"id": data.debtor_id, "company_id": company_id, "client_id": data.client_id}):
        raise HTTPException(status_code=400, detail="Nasabah tidak sesuai dengan klien atau perusahaan")

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
    token = auth_header[7:] if auth_header.startswith("Bearer ") else request.cookies.get(security.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi")
    try:
        payload = security.decode_access_token(token, JWT_SECRET)
        if payload.get("type") != "access" or not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Token tidak valid")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token tidak valid")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Pengguna tidak ditemukan")
    if user.get("status") == "nonaktif":
        raise HTTPException(status_code=403, detail="Akun Anda tidak aktif")
    if payload.get("ver", 0) != user.get("token_version", 0) or await db.revoked_tokens.find_one({"id": payload["jti"]}):
        raise HTTPException(status_code=401, detail="Sesi berakhir, silakan login kembali")
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
    password: str = Field(min_length=1, max_length=256)

class PasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=72)

class BusinessInput(BaseModel):
    model_config = ConfigDict(str_max_length=4000)

class ClientInput(BusinessInput):
    nama_perusahaan: str = Field(min_length=1, max_length=256, pattern=r"\S")
    alamat: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    nama_pic: Optional[str] = ""
    nomor_pic: Optional[str] = ""
    logo: Optional[str] = Field("", max_length=3_000_000)
    status: Literal["aktif", "nonaktif"] = "aktif"

class NasabahInput(BusinessInput):
    nama: str = Field(min_length=1, max_length=256, pattern=r"\S")
    nik: Optional[str] = ""
    telepon: Optional[str] = ""
    alamat: Optional[str] = ""
    provinsi: Optional[str] = ""
    kabupaten: Optional[str] = ""
    kecamatan: Optional[str] = ""
    kelurahan: Optional[str] = ""
    client_id: str
    status: str = "aktif"

class SuratKuasaInput(BusinessInput):
    nomor: str = Field(min_length=1, max_length=256, pattern=r"\S")
    client_id: str = Field(min_length=1, max_length=128, pattern=r"\S")
    tanggal_surat: Optional[str] = None
    tanggal_berlaku: Optional[str] = None
    tanggal_berakhir: Optional[str] = None
    file_url: Optional[str] = ""
    keterangan: Optional[str] = ""
    status: Literal["aktif", "nonaktif", "berakhir", "dicabut"] = "aktif"

class AccountInput(BusinessInput):
    nomor_kontrak: str = Field(min_length=1, max_length=256, pattern=r"\S")
    nama_debitur: str = Field(min_length=1, max_length=256, pattern=r"\S")
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
    debtor_id: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90, allow_inf_nan=False)
    longitude: Optional[float] = Field(None, ge=-180, le=180, allow_inf_nan=False)

class PetugasInput(BusinessInput):
    name: str = Field(min_length=1, max_length=256, pattern=r"\S")
    email: EmailStr
    password: Optional[str] = None
    telepon: Optional[str] = ""
    tim: Optional[str] = ""
    status: Literal["aktif", "nonaktif"] = "aktif"
    nik: Optional[str] = ""
    jabatan: Optional[str] = "PROFCOLL"
    no_sertifikasi: Optional[str] = ""
    sertifikasi_valid_until: Optional[str] = ""

class CompanyInput(BusinessInput):
    nama: str = Field(min_length=1, max_length=256, pattern=r"\S")
    alamat: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    city: Optional[str] = ""
    director_name: Optional[str] = ""
    director_position: Optional[str] = "DIREKTUR"
    company_code: Optional[str] = ""
    number_format: Optional[str] = "{sequence}/{company_code}/{month_name}/{year}"
    logo: Optional[str] = Field("", max_length=3_000_000)
    app_name: Optional[str] = "FieldCollector"

class PenugasanInput(BusinessInput):
    petugas_id: str
    account_id: str
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    catatan: Optional[str] = ""

class LoginBackgroundInput(BaseModel):
    preset: Literal["aurora", "blueprint", "sunrise", "image"] = "aurora"
    reset_image: bool = False


# Assignment status values (operational)
ASSIGNMENT_ACTIVE = "AKTIF"
ASSIGNMENT_TERMINAL = {"SELESAI", "DIBATALKAN", "KEDALUWARSA"}
# Map letter (document) status -> assignment status
LETTER_TO_ASSIGNMENT_STATUS = {
    "aktif": "AKTIF", "selesai": "SELESAI",
    "dibatalkan": "DIBATALKAN", "kedaluwarsa": "KEDALUWARSA",
}

class StatusUpdate(BaseModel):
    status: str

class ReviewInput(BaseModel):
    catatan_admin: Optional[str] = ""

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(data: LoginInput, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    moment = datetime.now(timezone.utc)
    bucket = security.rate_key(ip, str(int(moment.timestamp()) // 900))
    ip_limit = await db.rate_limits.find_one_and_update({"id": bucket}, {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": moment + timedelta(minutes=30)}}, upsert=True, return_document=True)
    if ip_limit.get("count", 0) > 30:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login. Coba lagi dalam 15 menit.", headers={"Retry-After": "900"})
    ident = security.rate_key(ip, email)
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Terlalu banyak percobaan. Coba lagi dalam 15 menit.")
        await db.login_attempts.delete_one({"identifier": ident})
    user = await db.users.find_one({"email": email})
    if not user or not await run_in_threadpool(verify_password, data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(), "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if user.get("status") == "nonaktif":
        raise HTTPException(status_code=403, detail="Akun Anda tidak aktif")
    await db.login_attempts.delete_one({"identifier": ident})
    token = create_access_token(user["id"], user["role"], user.get("token_version", 0))
    response.set_cookie(security.COOKIE_NAME, token, httponly=True, secure=security.PRODUCTION, samesite="lax", path="/api", max_age=security.TOKEN_HOURS * 3600)
    safe = clean(user)
    safe.pop("password_hash", None)
    await log_audit(user, "Login", "user", user["id"], request)
    return {"user": safe, **({"token": token} if not security.PRODUCTION else {})}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response, user: dict = Depends(get_current_user)):
    raw = request.headers.get("Authorization", "")
    token = raw[7:] if raw.startswith("Bearer ") else request.cookies.get(security.COOKIE_NAME)
    payload = security.decode_access_token(token, JWT_SECRET)
    await db.revoked_tokens.update_one({"id": payload["jti"]}, {"$set": {"expires_at": datetime.fromtimestamp(payload["exp"], timezone.utc)}}, upsert=True)
    response.delete_cookie(security.COOKIE_NAME, path="/api", secure=security.PRODUCTION, httponly=True, samesite="lax")
    return {"ok": True}

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@api_router.post("/auth/password")
async def change_own_password(data: PasswordInput, request: Request, response: Response, user: dict = Depends(get_current_user)):
    if len(data.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password maksimal 72 byte")
    async def update():
        current = await db.users.find_one({"id": user["id"], "company_id": user["company_id"]})
        if not current or not await run_in_threadpool(verify_password, data.current_password, current["password_hash"]):
            raise HTTPException(status_code=400, detail="Password saat ini salah")
        encoded = await run_in_threadpool(hash_password, data.new_password)
        await db.users.update_one({"id": user["id"], "company_id": user["company_id"]}, {"$set": {"password_hash": encoded, "updated_at": now_iso()}, "$inc": {"token_version": 1}})
        await log_audit(user, "Mengganti password sendiri", "user", user["id"], request)
    await transactions.run(client, update)
    response.delete_cookie(security.COOKIE_NAME, path="/api", secure=security.PRODUCTION, httponly=True, samesite="lax")
    return {"ok": True, "message": "Password diubah. Silakan login kembali."}


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
    today_d = datetime.now(timezone(timedelta(hours=7))).date()
    day_start = datetime.combine(today_d, datetime.min.time(), tzinfo=timezone(timedelta(hours=7))).astimezone(timezone.utc)
    today = day_start.isoformat()
    tomorrow = (day_start + timedelta(days=1)).isoformat()
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
        acc = r.get("account_snapshot") or await db.accounts.find_one({"id": r["account_id"], "company_id": user["company_id"]}, {"_id": 0})
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
        day = (datetime.now(timezone(timedelta(hours=7))).date() - timedelta(days=i))
        start_at = datetime.combine(day, datetime.min.time(), tzinfo=timezone(timedelta(hours=7))).astimezone(timezone.utc)
        start = start_at.isoformat()
        end = (start_at + timedelta(days=1)).isoformat()
        count = await db.field_reports.count_documents({"company_id": cid, "created_at": {"$gte": start, "$lt": end}})
        out.append({"date": day.isoformat(), "label": day.strftime("%d/%m"), "count": count})
    return out

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
async def delete_unused_record(collection_name, record_id, user, request, label, references, extra_filter=None):
    scope = {"id": record_id, "company_id": user["company_id"], **(extra_filter or {})}
    collection = getattr(db, collection_name)
    if not await collection.find_one(scope):
        raise HTTPException(status_code=404, detail=f"{label} tidak ditemukan")
    for ref_collection, field in references:
        if await getattr(db, ref_collection).find_one({"company_id": user["company_id"], field: record_id}):
            raise HTTPException(status_code=409, detail=f"{label} masih digunakan oleh data terkait. Hapus data terkait yang belum digunakan, atau nonaktifkan data ini.")
    await collection.delete_one(scope)
    await log_audit(user, f"Menghapus {label}", collection_name, record_id, request)
    return {"ok": True}


@api_router.delete("/clients/{record_id}")
@transactional
async def delete_client(record_id: str, request: Request, user: dict = Depends(admin_required)):
    return await delete_unused_record("clients", record_id, user, request, "Pemberi Kuasa", [
        ("power_of_attorneys", "client_id"), ("accounts", "client_id"),
        ("assignments", "client_id"), ("assignment_letters", "client_id"), ("debtors", "client_id")])


@api_router.delete("/surat-kuasa/{record_id}")
@transactional
async def delete_sk(record_id: str, request: Request, user: dict = Depends(admin_required)):
    return await delete_unused_record("power_of_attorneys", record_id, user, request, "Surat Kuasa", [
        ("accounts", "surat_kuasa_id"), ("assignments", "power_of_attorney_id"), ("assignment_letters", "surat_kuasa_id"), ("documents", "ref_id")])


@api_router.delete("/akun/{record_id}")
@transactional
async def delete_account(record_id: str, request: Request, user: dict = Depends(admin_required)):
    return await delete_unused_record("accounts", record_id, user, request, "Kontrak/Unit", [
        ("assignments", "account_id"), ("assignment_letters", "account_ids"), ("field_reports", "account_id")])


@api_router.delete("/petugas/{record_id}")
@transactional
async def delete_petugas(record_id: str, request: Request, user: dict = Depends(admin_required)):
    return await delete_unused_record("users", record_id, user, request, "Petugas", [
        ("assignments", "officer_id"), ("assignment_letters", "petugas_id"), ("field_reports", "petugas_id")], {"role": "petugas"})

@api_router.get("/clients")
async def list_clients(user: dict = Depends(admin_required), search: Optional[str] = None, response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    q = {"company_id": user["company_id"]}
    if search:
        q["nama_perusahaan"] = {"$regex": re.escape(search), "$options": "i"}
    items = await paged_documents(db.clients, q, response, page, limit)
    return items

@api_router.post("/clients")
@transactional
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
@transactional
async def update_client(client_id: str, data: ClientInput, request: Request, user: dict = Depends(admin_required)):
    doc = data.model_dump()
    doc["updated_at"] = now_iso()
    res = await db.clients.update_one({"id": client_id, "company_id": user["company_id"]}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    await log_audit(user, "Mengubah klien", "client", client_id, request)
    return await db.clients.find_one({"id": client_id}, {"_id": 0})

@api_router.patch("/clients/{client_id}/deactivate")
@transactional
async def deactivate_client(client_id: str, request: Request, user: dict = Depends(admin_required)):
    changed = await db.clients.update_one({"id": client_id, "company_id": user["company_id"]}, {"$set": {"status": "nonaktif", "updated_at": now_iso()}})
    if changed.matched_count == 0:
        raise HTTPException(status_code=404, detail="Klien tidak ditemukan")
    await log_audit(user, "Menonaktifkan klien", "client", client_id, request)
    return {"ok": True}

# ---------------------------------------------------------------------------
# Surat Kuasa
# ---------------------------------------------------------------------------
async def enrich_sk(sk: dict) -> dict:
    client_doc = await db.clients.find_one({"id": sk["client_id"], "company_id": sk["company_id"]}, {"_id": 0})
    sk["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    sk["total_akun"] = await db.accounts.count_documents({"surat_kuasa_id": sk["id"]})
    return sk

@api_router.get("/surat-kuasa")
async def list_sk(user: dict = Depends(admin_required), search: Optional[str] = None, response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    q = {"company_id": user["company_id"]}
    if search:
        q["nomor"] = {"$regex": re.escape(search), "$options": "i"}
    items = await paged_documents(db.power_of_attorneys, q, response, page, limit)
    return [await enrich_sk(i) for i in items]

@api_router.post("/surat-kuasa")
@transactional
async def create_sk(data: SuratKuasaInput, request: Request, user: dict = Depends(admin_required)):
    if data.file_url:
        raise HTTPException(status_code=400, detail="Buat Surat Kuasa terlebih dahulu, lalu unggah dokumennya")
    validate_assignment_dates(data.tanggal_berlaku, data.tanggal_berakhir)
    await validate_client_reference(data.client_id, user["company_id"])
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
    sk["accounts"] = await db.accounts.find({"surat_kuasa_id": sk_id, "company_id": user["company_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return sk

@api_router.put("/surat-kuasa/{sk_id}")
@transactional
async def update_sk(sk_id: str, data: SuratKuasaInput, request: Request, user: dict = Depends(admin_required)):
    validate_assignment_dates(data.tanggal_berlaku, data.tanggal_berakhir)
    await validate_client_reference(data.client_id, user["company_id"])
    existing = await db.power_of_attorneys.find_one({"id": sk_id, "company_id": user["company_id"]})
    if data.file_url and (not existing or data.file_url != existing.get("file_url", "")):
        raise HTTPException(status_code=400, detail="Gunakan unggahan PDF untuk mengganti dokumen Surat Kuasa")
    if existing and existing.get("client_id") != data.client_id:
        if await db.accounts.find_one({"surat_kuasa_id": sk_id, "company_id": user["company_id"]}) or await db.assignments.find_one({"power_of_attorney_id": sk_id, "company_id": user["company_id"]}):
            raise HTTPException(status_code=409, detail="Klien Surat Kuasa yang sudah memiliki unit tidak dapat diganti")
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
    client_doc = await db.clients.find_one({"id": acc["client_id"], "company_id": acc["company_id"]}, {"_id": 0})
    sk = await db.power_of_attorneys.find_one({"id": acc["surat_kuasa_id"], "company_id": acc["company_id"]}, {"_id": 0})
    acc["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    acc["surat_kuasa_nomor"] = sk["nomor"] if sk else "-"
    acc["surat_kuasa_file"] = sk.get("file_url", "") if sk else ""
    letter = await db.assignment_letters.find_one(
        {"account_ids": acc["id"], "status": "aktif", "company_id": acc["company_id"]}, {"_id": 0})
    if letter:
        petugas = await db.users.find_one({"id": letter["petugas_id"], "company_id": acc["company_id"]}, {"_id": 0})
        acc["petugas_name"] = petugas["name"] if petugas else "-"
        acc["letter_nomor"] = letter.get("nomor")
    else:
        acc["petugas_name"] = None
        acc["letter_nomor"] = None
    return acc


async def find_or_create_debtor(company_id: str, client_id: str, data: dict) -> str:
    nik = (data.get("nik") or "").strip()
    name = (data.get("nama_debitur") or data.get("nama") or "").strip()
    q = {"company_id": company_id, "client_id": client_id}
    q["nik"] = nik if nik else {"$in": ["", None]}
    if not nik:
        q["nama"] = name
    existing = await db.debtors.find_one(q)
    if existing:
        return existing["id"]
    did = new_id()
    await db.debtors.insert_one({
        "id": did, "company_id": company_id, "client_id": client_id,
        "nama": name, "nik": nik, "telepon": data.get("telepon", ""),
        "alamat": data.get("alamat", ""), "provinsi": data.get("provinsi", ""),
        "kabupaten": data.get("kabupaten", ""), "kecamatan": data.get("kecamatan", ""),
        "kelurahan": data.get("kelurahan", ""), "status": "aktif",
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return did

@api_router.get("/akun")
async def list_accounts(
    user: dict = Depends(admin_required),
    search: Optional[str] = None, client_id: Optional[str] = None,
    status: Optional[str] = None, provinsi: Optional[str] = None,
    surat_kuasa_id: Optional[str] = None, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=1000),
    available: bool = False,
):
    q = {"company_id": user["company_id"]}
    if available:
        occupied = await db.assignments.distinct("account_id", {"company_id": user["company_id"], "status": ASSIGNMENT_ACTIVE})
        q["id"] = {"$nin": occupied}
    if client_id:
        q["client_id"] = client_id
    if status:
        q["status"] = status
    if provinsi:
        q["provinsi"] = {"$regex": re.escape(provinsi), "$options": "i"}
    if surat_kuasa_id:
        q["surat_kuasa_id"] = surat_kuasa_id
    if search:
        q["$or"] = [
            {"nama_debitur": {"$regex": re.escape(search), "$options": "i"}},
            {"nomor_kontrak": {"$regex": re.escape(search), "$options": "i"}},
            {"nomor_polisi": {"$regex": re.escape(search), "$options": "i"}},
        ]
    total = await db.accounts.count_documents(q)
    skip = (page - 1) * limit
    items = await db.accounts.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    items = [await enrich_account(i) for i in items]
    return {"items": items, "total": total, "page": page, "limit": limit}

@api_router.post("/akun")
@transactional
async def create_account(data: AccountInput, request: Request, user: dict = Depends(admin_required)):
    await validate_account_references(data, user["company_id"])
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
@transactional
async def update_account(acc_id: str, data: AccountInput, request: Request, user: dict = Depends(admin_required)):
    await validate_account_references(data, user["company_id"])
    existing = await db.accounts.find_one({"id": acc_id, "company_id": user["company_id"]})
    if existing and any(existing.get(key) != getattr(data, key) for key in ("client_id", "surat_kuasa_id")):
        if await db.assignments.find_one({"account_id": acc_id, "company_id": user["company_id"], "status": ASSIGNMENT_ACTIVE}):
            raise HTTPException(status_code=409, detail="Tutup penugasan aktif sebelum mengganti klien atau Surat Kuasa unit")
    if existing:
        # Freeze legacy reports before master data changes, including ordinary name/address edits.
        await db.field_reports.update_many({"account_id": acc_id, "company_id": user["company_id"], "account_snapshot": {"$exists": False}}, {"$set": {"account_snapshot": clean(dict(existing))}})
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
async def list_petugas(user: dict = Depends(admin_required), response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    items = await paged_documents(db.users, {"company_id": user["company_id"], "role": "petugas"}, response, page, limit, {"_id": 0, "password_hash": 0})
    for item in items:
        item.pop("password_hash", None)
    for p in items:
        p["total_tugas"] = await db.assignment_letters.count_documents({"petugas_id": p["id"], "status": "aktif"})
    return items

@api_router.post("/petugas")
@transactional
async def create_petugas(data: PetugasInput, request: Request, user: dict = Depends(admin_required)):
    if not data.password:
        raise HTTPException(status_code=400, detail="Password wajib untuk petugas baru")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password wajib minimal 8 karakter")
    if len(data.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password maksimal 72 byte")
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah digunakan")
    seq = await next_sequence(f"petugas_{user['company_id']}")
    doc = {
        "id": new_id(), "company_id": user["company_id"], "role": "petugas",
        "name": data.name, "email": email,
        "password_hash": await run_in_threadpool(hash_password, data.password),
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
@transactional
async def update_petugas(pid: str, data: PetugasInput, request: Request, user: dict = Depends(admin_required)):
    if await db.users.find_one({"email": data.email.lower().strip(), "id": {"$ne": pid}}):
        raise HTTPException(status_code=400, detail="Email sudah digunakan")
    upd = {"name": data.name, "email": data.email.lower().strip(), "telepon": data.telepon, "tim": data.tim, "status": data.status,
           "nik": data.nik, "jabatan": data.jabatan, "no_sertifikasi": data.no_sertifikasi,
           "sertifikasi_valid_until": data.sertifikasi_valid_until, "updated_at": now_iso()}
    if data.password:
        if len(data.password) < 8:
            raise HTTPException(status_code=400, detail="Password wajib minimal 8 karakter")
        if len(data.password.encode("utf-8")) > 72:
            raise HTTPException(status_code=400, detail="Password maksimal 72 byte")
        upd["password_hash"] = await run_in_threadpool(hash_password, data.password)
    change = {"$set": upd}
    if data.password:
        change["$inc"] = {"token_version": 1}
    res = await db.users.update_one({"id": pid, "company_id": user["company_id"], "role": "petugas"}, change)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan")
    await log_audit(user, "Mengubah petugas", "user", pid, request)
    return await db.users.find_one({"id": pid}, {"_id": 0, "password_hash": 0})

# ---------------------------------------------------------------------------
# Penugasan -> Surat Tugas
# ---------------------------------------------------------------------------
async def enrich_letter(letter: dict) -> dict:
    petugas = await db.users.find_one({"id": letter["petugas_id"], "company_id": letter["company_id"]}, {"_id": 0, "password_hash": 0})
    client_doc = await db.clients.find_one({"id": letter.get("client_id"), "company_id": letter["company_id"]}, {"_id": 0})
    sk = await db.power_of_attorneys.find_one({"id": letter.get("surat_kuasa_id"), "company_id": letter["company_id"]}, {"_id": 0})
    letter["petugas_name"] = petugas["name"] if petugas else "-"
    letter["petugas_code"] = petugas["petugas_code"] if petugas else "-"
    letter["client_name"] = client_doc["nama_perusahaan"] if client_doc else "-"
    letter["surat_kuasa_nomor"] = sk["nomor"] if sk else "-"
    accs = await db.accounts.find({"id": {"$in": letter.get("account_ids", [])}, "company_id": letter["company_id"]}, {"_id": 0}).to_list(1000)
    letter["accounts"] = accs
    return letter

@api_router.post("/penugasan")
@transactional
async def create_penugasan(data: PenugasanInput, request: Request, user: dict = Depends(admin_required)):
    today = datetime.now(timezone(timedelta(hours=7))).date()
    _, end = validate_assignment_dates(data.valid_from or today.isoformat(), data.valid_until)
    if end and end < today:
        raise HTTPException(status_code=400, detail="Tanggal penugasan sudah berakhir")
    # 1 Assignment = 1 Unit = 1 Officer = 1 Assignment Letter
    petugas = await db.users.find_one({"id": data.petugas_id, "company_id": user["company_id"], "role": "petugas"})
    if not petugas:
        raise HTTPException(status_code=404, detail="Petugas tidak ditemukan")
    if petugas.get("status") != "aktif":
        raise HTTPException(status_code=400, detail="Petugas tidak aktif")
    acc = await db.accounts.find_one({"id": data.account_id, "company_id": user["company_id"]}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Unit/akun tidak ditemukan")

    # Rule: a unit may only have ONE active assignment at a time.
    active = await db.assignments.find_one({"account_id": data.account_id, "status": ASSIGNMENT_ACTIVE})
    if active:
        raise HTTPException(
            status_code=400,
            detail="Unit ini masih memiliki penugasan AKTIF. Selesaikan atau batalkan penugasan lama terlebih dahulu.",
        )

    # Business rule: Surat Kuasa harus aktif
    sk_id = acc["surat_kuasa_id"]
    sk = await db.power_of_attorneys.find_one({"id": sk_id, "company_id": user["company_id"], "client_id": acc["client_id"]})
    if not sk or sk.get("status") != "aktif":
        raise HTTPException(status_code=400, detail="Surat Kuasa tidak aktif, tidak dapat membuat Penugasan")
    start, end = validate_assignment_dates(data.valid_from or today.isoformat(), data.valid_until or sk.get("tanggal_berakhir"))
    sk_start, sk_end = validate_assignment_dates(sk.get("tanggal_berlaku"), sk.get("tanggal_berakhir"))
    if (sk_start and start < sk_start) or (sk_end and (start > sk_end or (end and end > sk_end))):
        raise HTTPException(status_code=400, detail="Masa penugasan harus berada dalam masa berlaku Surat Kuasa")
    client_doc = await db.clients.find_one({"id": acc["client_id"], "company_id": user["company_id"]})
    if not client_doc or client_doc.get("status", "aktif") != "aktif":
        raise HTTPException(status_code=400, detail="Klien tidak aktif, tidak dapat membuat penugasan")
    client_id = acc["client_id"]
    if transactions.session_context.get() is not None:
        for collection, identity in ((db.clients, client_id), (db.power_of_attorneys, sk_id), (db.users, data.petugas_id)):
            await collection.update_one({"id": identity, "company_id": user["company_id"]}, {"$inc": {"relation_version": 1}})

    now = datetime.now(timezone.utc)
    year = now.year
    # Internal operational identifier (not the official document number)
    aseq = await next_sequence(f"asg_{user['company_id']}_{year}_{now.month}")
    assignment_number = f"AS/FC/{year}/{now.month:02d}/{aseq:04d}"

    # Official document number (single official number, generated immediately -- no manual finalize step)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    dseq = await next_sequence(f"docnum_{user['company_id']}_{year}")
    fmt = company.get("number_format") or "{sequence}/{company_code}/{month_name}/{year}"
    try:
        document_number = fmt.format(sequence=f"{dseq:04d}", company_code=company.get("company_code", ""),
                                     month_name=ID_MONTHS_UP[now.month], year=year)
    except (KeyError, IndexError, ValueError):
        document_number = f"{dseq:04d}/{company.get('company_code', '')}/{ID_MONTHS_UP[now.month]}/{year}"
    generate_code = f"GNR-{year}-{uuid.uuid4().hex[:20].upper()}"
    reg_seq = await next_sequence(f"bastk_{user['company_id']}_{year}")
    register_number = f"{reg_seq}/{int_to_roman(year)}/{MONTH_ROMAN[now.month]}"

    valid_from = data.valid_from or today.isoformat()
    valid_until = data.valid_until or sk.get("tanggal_berakhir") or None

    assignment_id = new_id()
    letter_id = new_id()

    # --- Assignment: the MAIN operational transaction ---
    assignment = {
        "id": assignment_id, "company_id": user["company_id"],
        "active_key": f"{user['company_id']}:{data.account_id}",
        "account_id": data.account_id, "officer_id": data.petugas_id,
        "power_of_attorney_id": sk_id, "client_id": client_id,
        "status": ASSIGNMENT_ACTIVE,
        "valid_from": valid_from, "valid_until": valid_until,
        "note": data.catatan or "",
        "assignment_number": assignment_number,
        "assignment_letter_id": letter_id,
        "created_by": user["id"], "created_at": now_iso(), "updated_at": now_iso(),
    }
    # --- Assignment Letter: the official document generated FROM the assignment ---
    letter = {
        "id": letter_id, "company_id": user["company_id"], "assignment_id": assignment_id,
        "nomor": document_number,  # legacy display field now mirrors official document_number
        "document_number": document_number, "generate_code": generate_code,
        "register_number": register_number, "issue_date": now.date().isoformat(),
        "petugas_id": data.petugas_id, "client_id": client_id, "surat_kuasa_id": sk_id,
        "account_id": data.account_id, "account_ids": [data.account_id],
        "tanggal": valid_from, "masa_berlaku": valid_until, "catatan": data.catatan or "",
        "status": "aktif", "document_status": "ACTIVE", "template_version": "v1",
        "generated_by": user["name"], "generated_at": now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    snapshot = await build_document_data(letter, user["name"])
    letter["document_snapshot"] = snapshot
    letter["snapshot_data"] = snapshot  # task-named alias
    try:
        await db.assignments.insert_one(assignment)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Unit ini masih memiliki penugasan AKTIF")
    try:
        await db.assignment_letters.insert_one(letter)
    except Exception:
        if transactions.session_context.get() is None:
            await db.assignments.delete_one({"id": assignment_id, "company_id": user["company_id"]})
        raise

    await db.accounts.update_one({"id": data.account_id, "company_id": user["company_id"]}, {"$set": {"status": "DITUGASKAN", "active_assignment_id": assignment_id, "updated_at": now_iso()}})
    await log_audit(user, "Membuat penugasan", "assignment", assignment_id, request)
    await log_audit(user, "Menerbitkan Surat Penugasan", "assignment_letter", letter_id, request)

    out = await enrich_letter(clean(letter))
    out["assignment_id"] = assignment_id
    out["assignment_number"] = assignment_number
    out["document_number"] = document_number
    return out

@api_router.get("/surat-tugas")
async def list_surat_tugas(user: dict = Depends(admin_required), search: Optional[str] = None, petugas_id: Optional[str] = None, status: Optional[str] = None, response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    q = {"company_id": user["company_id"]}
    if search:
        q["nomor"] = {"$regex": re.escape(search), "$options": "i"}
    if petugas_id:
        q["petugas_id"] = petugas_id
    if status:
        q["status"] = status
    items = await paged_documents(db.assignment_letters, q, response, page, limit)
    return [await enrich_letter(i) for i in items]

@api_router.get("/surat-tugas/{lid}")
async def get_surat_tugas(lid: str, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]}, {"_id": 0})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    return await enrich_letter(letter)

@api_router.patch("/surat-tugas/{lid}/status")
@transactional
async def update_st_status(lid: str, data: StatusUpdate, request: Request, user: dict = Depends(admin_required)):
    if data.status not in LETTER_TO_ASSIGNMENT_STATUS:
        raise HTTPException(status_code=400, detail="Status Surat Tugas tidak valid")
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    if letter.get("status") == data.status:
        return await enrich_letter(clean(letter))
    if letter.get("status") != "aktif":
        raise HTTPException(status_code=400, detail="Status Surat Tugas yang sudah berakhir tidak dapat diubah. Buat penugasan baru.")
    document_status = {"aktif": "ACTIVE", "selesai": "COMPLETED", "dibatalkan": "CANCELLED", "kedaluwarsa": "EXPIRED"}[data.status]
    changed = await db.assignment_letters.update_one({"id": lid, "company_id": user["company_id"], "status": "aktif"}, {"$set": {"status": data.status, "document_status": document_status, "updated_at": now_iso()}})
    if changed.matched_count == 0:
        raise HTTPException(status_code=409, detail="Status tugas telah berubah. Muat ulang data.")
    # Keep the operational assignment in sync (assignment is the primary object)
    if letter.get("assignment_id"):
        assignment_update = {"$set": {"status": LETTER_TO_ASSIGNMENT_STATUS[data.status], "updated_at": now_iso()}}
        if data.status != "aktif":
            assignment_update["$unset"] = {"active_key": ""}
        await db.assignments.update_one(
            {"id": letter["assignment_id"], "company_id": user["company_id"]},
            assignment_update,
        )
    if data.status != "aktif":
        await db.accounts.update_many(
            {"id": {"$in": letter.get("account_ids", [])}, "company_id": user["company_id"], "status": "DITUGASKAN", "$or": [{"active_assignment_id": letter.get("assignment_id")}, {"active_assignment_id": {"$exists": False}}]},
            {"$set": {"status": "BELUM_DITUGASKAN", "updated_at": now_iso()}, "$unset": {"active_assignment_id": ""}},
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
    valid = letter["status"] == "aktif" and not letter_is_expired(letter)
    return {
        "valid": valid,
        "nomor": letter["nomor"],
        "petugas_name": petugas["name"] if petugas else "-",
        "company_name": company["nama"] if company else "-",
        "tanggal_berlaku": letter.get("masa_berlaku") or letter.get("tanggal"),
        "status": "kedaluwarsa" if letter["status"] == "aktif" and letter_is_expired(letter) else letter["status"],
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
    officer = await db.users.find_one({"id": letter["petugas_id"], "company_id": letter["company_id"]}, {"_id": 0, "password_hash": 0}) or {}
    client_doc = await db.clients.find_one({"id": letter.get("client_id"), "company_id": letter["company_id"]}, {"_id": 0}) or {}
    accs = await db.accounts.find({"id": {"$in": letter.get("account_ids", [])}, "company_id": letter["company_id"]}, {"_id": 0}).to_list(1000)
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
        from seed import _default_template
        template = _default_template(letter["company_id"])
    if letter.get("document_snapshot"):
        data = letter["document_snapshot"]
    else:
        data = await build_document_data(letter)
    return {
        "document_status": letter.get("document_status", "DRAFT"),
        "is_finalized": letter.get("document_status") in {"ACTIVE", "COMPLETED", "CANCELLED", "EXPIRED"},
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
@transactional
async def finalize_document(lid: str, request: Request, user: dict = Depends(admin_required)):
    letter = await db.assignment_letters.find_one({"id": lid, "company_id": user["company_id"]})
    if not letter:
        raise HTTPException(status_code=404, detail="Surat Tugas tidak ditemukan")
    if letter.get("status") in {"selesai", "dibatalkan", "kedaluwarsa"}:
        raise HTTPException(status_code=400, detail="Surat Tugas yang sudah berakhir tidak dapat diterbitkan ulang")
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
    if st == "aktif" and letter_is_expired(letter):
        st = "kedaluwarsa"
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
@transactional
async def update_company(data: CompanyInput, request: Request, user: dict = Depends(admin_required)):
    changed = await db.companies.update_one({"id": user["company_id"]}, {"$set": {**data.model_dump(), "updated_at": now_iso()}})
    if changed.matched_count == 0:
        raise HTTPException(status_code=404, detail="Perusahaan tidak ditemukan")
    await log_audit(user, "Mengubah profil perusahaan", "company", user["company_id"], request)
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})


# ---------------------------------------------------------------------------
# Petugas (field officer) views
# ---------------------------------------------------------------------------
@api_router.get("/my/tugas")
async def my_tugas(user: dict = Depends(petugas_required), response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    # Officer tasks load from the ASSIGNMENTS collection (not the letters).
    assignments = await paged_documents(db.assignments, {"officer_id": user["id"], "company_id": user["company_id"], "status": ASSIGNMENT_ACTIVE}, response, page, limit)
    result = []
    for a in assignments:
        acc = await db.accounts.find_one({"id": a["account_id"], "company_id": user["company_id"]}, {"_id": 0})
        if not acc:
            continue
        sk = await db.power_of_attorneys.find_one({"id": a.get("power_of_attorney_id"), "company_id": user["company_id"]}, {"_id": 0})
        client_doc = await db.clients.find_one({"id": acc.get("client_id"), "company_id": user["company_id"]}, {"_id": 0})
        letter = await db.assignment_letters.find_one({"assignment_id": a["id"]}, {"_id": 0})
        rep = await db.field_reports.find_one({"assignment_id": a["id"]}, {"_id": 0})
        doc_no = (letter.get("document_number") or letter.get("nomor")) if letter else a.get("assignment_number")
        result.append({
            **task_availability(a, sk, client_doc),
            "account": acc,
            "assignment_id": a["id"],
            "letter_id": letter["id"] if letter else None,
            "letter_nomor": doc_no,
            "document_number": letter.get("document_number") if letter else None,
            "assignment_number": a.get("assignment_number"),
            "surat_kuasa_nomor": sk["nomor"] if sk else "-",
            "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
            "catatan_admin": a.get("note", ""),
            "sudah_dilaporkan": rep is not None,
        })
    return result

@api_router.get("/my/tugas/{account_id}")
async def my_tugas_detail(account_id: str, user: dict = Depends(petugas_required)):
    a = await db.assignments.find_one(
        {"officer_id": user["id"], "company_id": user["company_id"], "account_id": account_id, "status": ASSIGNMENT_ACTIVE}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Tugas tidak ditemukan")
    acc = await db.accounts.find_one({"id": account_id, "company_id": user["company_id"]}, {"_id": 0})
    if not acc:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    sk = await db.power_of_attorneys.find_one({"id": a.get("power_of_attorney_id"), "company_id": user["company_id"]}, {"_id": 0})
    client_doc = await db.clients.find_one({"id": acc.get("client_id"), "company_id": user["company_id"]}, {"_id": 0})
    letter = await db.assignment_letters.find_one({"assignment_id": a["id"]}, {"_id": 0})
    rep = await db.field_reports.find_one({"assignment_id": a["id"]}, {"_id": 0})
    doc_no = (letter.get("document_number") or letter.get("nomor")) if letter else a.get("assignment_number")
    await log_audit(user, "Membuka tugas", "assignment", a["id"])
    return {
        **task_availability(a, sk, client_doc),
        "account": acc,
        "assignment_id": a["id"],
        "letter_id": letter["id"] if letter else None,
        "letter_nomor": doc_no,
        "document_number": letter.get("document_number") if letter else None,
        "surat_kuasa_nomor": sk["nomor"] if sk else "-",
        "surat_kuasa_file": sk.get("file_url", "") if sk else "",
        "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
        "catatan_admin": a.get("note", ""),
        "existing_report": rep,
    }

@api_router.get("/my/riwayat")
async def my_riwayat(user: dict = Depends(petugas_required), status: Optional[str] = None, assignment_id: Optional[str] = None, response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000)):
    q = {"petugas_id": user["id"], "company_id": user["company_id"]}
    if status:
        q["status"] = status
    if assignment_id:
        q["assignment_id"] = assignment_id
    reports = await paged_documents(db.field_reports, q, response, page, limit)
    for r in reports:
        acc = r.get("account_snapshot") or await db.accounts.find_one({"id": r["account_id"], "company_id": user["company_id"]}, {"_id": 0})
        letter = None
        if r.get("assignment_id"):
            letter = await db.assignment_letters.find_one({"assignment_id": r["assignment_id"], "company_id": user["company_id"]}, {"_id": 0})
        if not letter and r.get("assignment_letter_id"):
            letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"], "company_id": user["company_id"]}, {"_id": 0})
        r["nama_debitur"] = acc["nama_debitur"] if acc else "-"
        r["nomor_polisi"] = acc["nomor_polisi"] if acc else "-"
        r["letter_nomor"] = (letter.get("document_number") or letter.get("nomor")) if letter else "-"
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
    account_id: str = Form(...),
    status: str = Form(...),
    catatan: str = Form(...),
    assignment_id: Optional[str] = Form(None),
    assignment_letter_id: Optional[str] = Form(None),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    lokasi_alasan: Optional[str] = Form(None),
    photos: List[UploadFile] = File(default=[]),
    user: dict = Depends(petugas_required),
):
    # Resolve the assignment (primary relation). Accept legacy assignment_letter_id for compatibility.
    assignment = None
    if assignment_id:
        assignment = await db.assignments.find_one({"id": assignment_id, "officer_id": user["id"], "company_id": user["company_id"]})
    if not assignment and assignment_letter_id:
        letter_tmp = await db.assignment_letters.find_one({"id": assignment_letter_id, "petugas_id": user["id"], "company_id": user["company_id"]})
        if letter_tmp and letter_tmp.get("assignment_id"):
            assignment = await db.assignments.find_one({"id": letter_tmp["assignment_id"], "officer_id": user["id"], "company_id": user["company_id"]})
    if not assignment:
        raise HTTPException(status_code=404, detail="Penugasan tidak ditemukan")
    if assignment.get("status") != ASSIGNMENT_ACTIVE:
        raise HTTPException(status_code=400, detail="Penugasan tidak aktif")
    start, end = validate_assignment_dates(assignment.get("valid_from"), assignment.get("valid_until"))
    today = datetime.now(timezone(timedelta(hours=7))).date()
    if (start and start > today) or (end and end < today):
        raise HTTPException(status_code=400, detail="Penugasan di luar masa berlaku")
    if assignment.get("account_id") != account_id:
        raise HTTPException(status_code=403, detail="Akun ini bukan bagian dari tugas Anda")
    if assignment.get("power_of_attorney_id"):
        authority = await db.power_of_attorneys.find_one({"id": assignment["power_of_attorney_id"], "company_id": user["company_id"]})
        if not authority:
            raise HTTPException(status_code=400, detail="Surat Kuasa tidak ditemukan")
        client_doc = await db.clients.find_one({"id": assignment.get("client_id"), "company_id": user["company_id"]})
        availability = task_availability(assignment, authority, client_doc)
        if not availability["can_report"]:
            raise HTTPException(status_code=400, detail=availability["blocked_reason"])
    letter = await db.assignment_letters.find_one({"assignment_id": assignment["id"]}, {"_id": 0})
    existing = await db.field_reports.find_one({"assignment_id": assignment["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Laporan untuk tugas ini sudah dikirim")
    if len(catatan.strip()) < 10:
        raise HTTPException(status_code=400, detail="Catatan petugas wajib minimal 10 karakter")
    if len(catatan) > 4000:
        raise HTTPException(status_code=400, detail="Catatan petugas maksimal 4000 karakter")
    if status not in ACCOUNT_STATUS_MAP:
        raise HTTPException(status_code=400, detail="Status hasil kunjungan tidak valid")
    lat, lng = validate_report_location(latitude, longitude, lokasi_alasan)
    photos = [p for p in photos if p and p.filename]
    if status == "UNIT_DITEMUKAN" and len(photos) < 1:
        raise HTTPException(status_code=400, detail="Foto bukti wajib minimal 1 untuk unit ditemukan")
    if len(photos) > 5:
        raise HTTPException(status_code=400, detail="Maksimal 5 foto")

    report_id = new_id()
    saved = []
    validated_photos = []
    for p in photos:
        if p.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Format foto tidak diizinkan (hanya JPG/PNG/WEBP)")
        content = await p.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Ukuran foto maksimal 8MB")
        actual_format = await run_in_threadpool(verified_image_format, content, {"JPEG", "PNG", "WEBP"}, 20_000_000)
        ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[actual_format]
        validated_photos.append((content, ext, {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[ext]))
    for content, ext, content_type in validated_photos:
        obj_path = f"{APP_NAME}/companies/{user['company_id']}/reports/{report_id}/{new_id()}.{ext}"
        await db.upload_intents.insert_one({"id": obj_path, "storage_path": obj_path, "company_id": user["company_id"], "created_at": datetime.now(timezone.utc)})
        result = await run_in_threadpool(put_object, obj_path, content, content_type)
        saved.append({"storage_path": result["path"], "url": f"/api/files/{result['path']}"})

    report = {
        "id": report_id, "company_id": user["company_id"], "petugas_id": user["id"],
        "assignment_id": assignment["id"],
        "submission_key": assignment["id"],
        "assignment_letter_id": letter["id"] if letter else assignment_letter_id,
        "account_id": account_id,
        "status": status, "catatan": catatan,
        "latitude": lat,
        "longitude": lng,
        "lokasi_alasan": lokasi_alasan or "",
        "report_status": "SUBMITTED",
        "catatan_admin": "", "reviewed": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    async def persist_report():
        # Claim the assignment inside the transaction so cancellation/reporting
        # and officer deactivation cannot commit contradictory results.
        live = await db.assignments.find_one({"id": assignment["id"], "company_id": user["company_id"], "officer_id": user["id"], "status": ASSIGNMENT_ACTIVE})
        if not live or live.get("status") != ASSIGNMENT_ACTIVE:
            raise HTTPException(status_code=409, detail="Penugasan telah berubah. Muat ulang tugas sebelum melapor.")
        if transactions.session_context.get() is not None:
            officer = await db.users.find_one({"id": user["id"], "company_id": user["company_id"], "status": "aktif"})
            if not officer:
                raise HTTPException(status_code=403, detail="Akun Anda tidak aktif")
            await db.users.update_one({"id": user["id"], "company_id": user["company_id"]}, {"$inc": {"relation_version": 1}})
            authority = await db.power_of_attorneys.find_one({"id": live.get("power_of_attorney_id"), "company_id": user["company_id"]})
            client_doc = await db.clients.find_one({"id": live.get("client_id"), "company_id": user["company_id"]})
            if not authority or not client_doc:
                raise HTTPException(status_code=409, detail="Data kuasa atau klien sudah berubah")
            availability = task_availability(live, authority, client_doc)
            if not availability["can_report"]:
                raise HTTPException(status_code=409, detail=availability["blocked_reason"])
            for collection, identity in ((db.clients, live["client_id"]), (db.power_of_attorneys, live["power_of_attorney_id"])):
                await collection.update_one({"id": identity, "company_id": user["company_id"]}, {"$inc": {"relation_version": 1}})
        await db.assignments.update_one({"id": assignment["id"], "company_id": user["company_id"], "status": ASSIGNMENT_ACTIVE}, {"$inc": {"report_version": 1}})
        snapshot = await db.accounts.find_one({"id": account_id, "company_id": user["company_id"]}, {"_id": 0})
        if transactions.session_context.get() is not None and not snapshot:
            raise HTTPException(status_code=409, detail="Unit sudah tidak tersedia")
        if snapshot:
            report["account_snapshot"] = snapshot
        try:
            await db.field_reports.insert_one(dict(report))
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="Laporan untuk tugas ini sudah dikirim")
        for ph in saved:
            await db.report_photos.insert_one({"id": new_id(), "report_id": report_id, "url": ph["url"], "storage_path": ph["storage_path"], "created_at": now_iso()})
            await db.upload_intents.delete_one({"id": ph["storage_path"], "company_id": user["company_id"]})
        await db.accounts.update_one({"id": account_id, "company_id": user["company_id"]}, {"$set": {"status": ACCOUNT_STATUS_MAP.get(status, "DALAM_PROSES"), "updated_at": now_iso()}})
        await log_audit(user, f"Mengirim laporan ({status})", "field_report", report_id, request)
    await transactions.run(client, persist_report)
    out = clean(report)
    out["photos"] = [{"url": s["url"]} for s in saved]
    return out

@api_router.get("/laporan")
async def list_laporan(
    user: dict = Depends(admin_required),
    petugas_id: Optional[str] = None, client_id: Optional[str] = None,
    status: Optional[str] = None, tanggal: Optional[str] = None,
    provinsi: Optional[str] = None, search: Optional[str] = None,
    response: Response = None, page: int = Query(1, ge=1), limit: int = Query(500, ge=1, le=1000),
):
    q = {"company_id": user["company_id"]}
    if petugas_id:
        q["petugas_id"] = petugas_id
    if status:
        q["status"] = status
    if tanggal:
        try:
            report_day = date.fromisoformat(tanggal)
        except ValueError:
            raise HTTPException(status_code=400, detail="Tanggal laporan tidak valid (YYYY-MM-DD)")
        begin = datetime.combine(report_day, datetime.min.time(), tzinfo=timezone(timedelta(hours=7))).astimezone(timezone.utc)
        q["created_at"] = {"$gte": begin.isoformat(), "$lt": (begin + timedelta(days=1)).isoformat()}
    clauses = []
    if client_id:
        ids = await db.assignment_letters.distinct("id", {"company_id": user["company_id"], "client_id": client_id})
        clauses.append({"assignment_letter_id": {"$in": ids}})
    if provinsi:
        pattern = {"$regex": re.escape(provinsi), "$options": "i"}
        ids = await db.accounts.distinct("id", {"company_id": user["company_id"], "provinsi": pattern})
        clauses.append({"$or": [{"account_snapshot.provinsi": pattern}, {"account_snapshot": {"$exists": False}, "account_id": {"$in": ids}}]})
    if search:
        pattern = {"$regex": re.escape(search), "$options": "i"}
        account_ids = await db.accounts.distinct("id", {"company_id": user["company_id"], "$or": [{"nama_debitur": pattern}, {"nomor_polisi": pattern}]})
        letter_ids = await db.assignment_letters.distinct("id", {"company_id": user["company_id"], "nomor": pattern})
        clauses.append({"$or": [{"account_snapshot.nama_debitur": pattern}, {"account_snapshot.nomor_polisi": pattern}, {"account_snapshot": {"$exists": False}, "account_id": {"$in": account_ids}}, {"assignment_letter_id": {"$in": letter_ids}}]})
    if clauses:
        q["$and"] = clauses
    reports = await paged_documents(db.field_reports, q, response, page, limit)
    result = []
    for r in reports:
        acc = r.get("account_snapshot") or await db.accounts.find_one({"id": r["account_id"], "company_id": user["company_id"]}, {"_id": 0})
        letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"], "company_id": user["company_id"]}, {"_id": 0})
        petugas = await db.users.find_one({"id": r["petugas_id"], "company_id": user["company_id"]}, {"_id": 0, "password_hash": 0})
        client_doc = await db.clients.find_one({"id": letter["client_id"], "company_id": user["company_id"]}, {"_id": 0}) if letter else None
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
    acc = r.get("account_snapshot") or await db.accounts.find_one({"id": r["account_id"], "company_id": user["company_id"]}, {"_id": 0})
    letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"], "company_id": user["company_id"]}, {"_id": 0})
    petugas = await db.users.find_one({"id": r["petugas_id"], "company_id": user["company_id"]}, {"_id": 0, "password_hash": 0})
    client_doc = await db.clients.find_one({"id": letter["client_id"], "company_id": user["company_id"]}, {"_id": 0}) if letter else None
    photos = await db.report_photos.find({"report_id": rid}, {"_id": 0}).to_list(10)
    await log_audit(user, "Melihat laporan", "field_report", rid)
    return {
        **r, "account": acc, "petugas_name": petugas["name"] if petugas else "-",
        "letter_nomor": letter["nomor"] if letter else "-",
        "client_name": client_doc["nama_perusahaan"] if client_doc else "-",
        "photos": photos,
    }

@api_router.patch("/laporan/{rid}/review")
@transactional
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
    if not c:
        raise HTTPException(status_code=404, detail="Perusahaan tidak ditemukan")
    return c

@api_router.get("/branding")
async def get_branding():
    """Public branding (app name + logo) for the login page and shell."""
    c = await db.companies.find_one({}, {"_id": 0}) or {}
    background = c.get("login_background") or {}
    return {
        "app_name": c.get("app_name") or "FieldCollector",
        "logo": c.get("logo") or "",
        "company_name": c.get("nama") or "",
        "login_background": {
            "preset": background.get("preset", "aurora"),
            "image_url": f"/api/branding/login-background?v={background.get('version', '')}" if background.get("image") else "",
        },
    }

@api_router.get("/branding/login-background")
async def get_login_background_image():
    company = await db.companies.find_one({}, {"login_background": 1}) or {}
    image = (company.get("login_background") or {}).get("image", "")
    if not image:
        raise HTTPException(status_code=404, detail="Background login belum diunggah")
    content = base64.b64decode(image.split(",", 1)[1])
    return Response(content=content, media_type="image/jpeg", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })

@api_router.put("/company/login-background")
@transactional
async def update_login_background(data: LoginBackgroundInput, user: dict = Depends(admin_required)):
    company = await db.companies.find_one({"id": user["company_id"]})
    if not company:
        raise HTTPException(status_code=404, detail="Perusahaan tidak ditemukan")
    background = company.get("login_background") or {}
    if data.preset == "image" and (not background.get("image") or data.reset_image):
        raise HTTPException(status_code=400, detail="Unggah gambar background terlebih dahulu")
    update = {"login_background.preset": data.preset, "updated_at": now_iso()}
    if data.reset_image:
        update.update({"login_background.image": "", "login_background.version": new_id()})
    await db.companies.update_one({"id": user["company_id"]}, {"$set": update})
    await log_audit(user, "Mengubah background login", "company", user["company_id"])
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

def prepare_login_background(content: bytes, content_type: str) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as source:
            expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
            if source.format != expected.get(content_type) or source.width * source.height > 20_000_000:
                raise HTTPException(status_code=400, detail="Gambar tidak valid atau resolusinya terlalu besar (maks 20 megapiksel)")
            image = ImageOps.exif_transpose(source)
            image.thumbnail((2560, 1600))
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                image = Image.new("RGB", rgba.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
            else:
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, ValueError):
        raise HTTPException(status_code=400, detail="Gambar tidak dapat dibaca. Gunakan JPG, PNG, atau WEBP")

@api_router.post("/company/login-background")
async def upload_login_background(file: UploadFile = File(...), user: dict = Depends(admin_required)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Gunakan gambar JPG, PNG, atau WEBP")
    content = await file.read(3 * 1024 * 1024 + 1)
    if len(content) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran background maksimal 3MB")
    if not await db.companies.find_one({"id": user["company_id"]}):
        raise HTTPException(status_code=404, detail="Perusahaan tidak ditemukan")
    image = await run_in_threadpool(prepare_login_background, content, file.content_type)
    background = {"preset": "image", "image": "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii"), "version": new_id()}
    return await store_company_artifact(user, {"login_background": background}, "Mengunggah background login")


async def store_company_artifact(user, values, action):
    async def persist():
        changed = await db.companies.update_one({"id": user["company_id"]}, {"$set": {**values, "updated_at": now_iso()}})
        if changed.matched_count == 0:
            raise HTTPException(status_code=404, detail="Perusahaan tidak ditemukan")
        await log_audit(user, action, "company", user["company_id"])
        return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return await transactions.run(client, persist)

@api_router.post("/company/logo")
async def upload_company_logo(file: UploadFile = File(...), user: dict = Depends(admin_required)):
    if file.content_type not in ("image/png",):
        raise HTTPException(status_code=400, detail="Logo harus file PNG transparan")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran logo maksimal 2MB")
    await run_in_threadpool(verified_image_format, content, {"PNG"}, 4_000_000)
    data_url = "data:image/png;base64," + base64.b64encode(content).decode("ascii")
    return await store_company_artifact(user, {"logo": data_url}, "Mengunggah logo perusahaan")

@api_router.post("/surat-kuasa/{sk_id}/file")
async def upload_sk_file(sk_id: str, file: UploadFile = File(...), user: dict = Depends(admin_required)):
    sk = await db.power_of_attorneys.find_one({"id": sk_id, "company_id": user["company_id"]})
    if not sk:
        raise HTTPException(status_code=404, detail="Surat Kuasa tidak ditemukan")
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="File Surat Kuasa harus PDF")
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 8MB")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")
    try:
        await run_in_threadpool(validate_pdf, content)
    except Exception:
        raise HTTPException(status_code=400, detail="PDF rusak, terenkripsi, atau memuat konten aktif. Gunakan PDF tanpa script dan lampiran.")
    obj_path = f"{APP_NAME}/companies/{user['company_id']}/surat-kuasa/{sk_id}/{new_id()}.pdf"
    await db.upload_intents.insert_one({"id": obj_path, "storage_path": obj_path, "company_id": user["company_id"], "created_at": datetime.now(timezone.utc)})
    result = await run_in_threadpool(put_object, obj_path, content, "application/pdf")
    file_url = f"/api/files/{result['path']}"
    async def persist_document():
        changed = await db.power_of_attorneys.update_one({"id": sk_id, "company_id": user["company_id"]}, {"$set": {"file_url": file_url, "updated_at": now_iso()}})
        if changed.matched_count == 0:
            raise HTTPException(status_code=409, detail="Surat Kuasa sudah berubah atau dihapus")
        await db.documents.insert_one({"id": new_id(), "company_id": user["company_id"], "kind": "surat_kuasa", "ref_id": sk_id, "storage_path": result["path"], "url": file_url, "filename": file.filename, "created_at": now_iso()})
        await db.upload_intents.delete_one({"id": obj_path, "company_id": user["company_id"]})
        await log_audit(user, "Mengunggah dokumen Surat Kuasa", "surat_kuasa", sk_id)
    await transactions.run(client, persist_document)
    return {"file_url": file_url}

# ---------------------------------------------------------------------------
# Private file proxy; cookie/Bearer authentication and tenant/assignment ownership.
# ---------------------------------------------------------------------------
@api_router.get("/files/{path:path}")
async def serve_file(path: str, user: dict = Depends(get_current_user)):
    record = await db.report_photos.find_one({"storage_path": path})
    if record:
        owner_query = {"id": record["report_id"], "company_id": user["company_id"]}
        if user.get("role") != "admin":
            owner_query["petugas_id"] = user["id"]
        owner = await db.field_reports.find_one(owner_query)
    else:
        record = await db.documents.find_one({"storage_path": path, "company_id": user["company_id"]})
        owner = record if user.get("role") == "admin" else None
        if record and user.get("role") == "petugas" and record.get("kind") == "surat_kuasa":
            owner = await db.assignments.find_one({"company_id": user["company_id"], "officer_id": user["id"], "power_of_attorney_id": record.get("ref_id"), "status": ASSIGNMENT_ACTIVE})
    if not record or not owner:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    try:
        data, content_type = await run_in_threadpool(get_object, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File tidak ditemukan di penyimpanan")
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------
import chat
import sys
chat.register(api_router, sys.modules[__name__])
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Next-Page", "X-Total-Count"],
)

async def migrate_assignments_non_destructive():
    """Non-destructive, idempotent. Ensures every legacy assignment_letter has a
    matching single-unit assignment, and backfills field_reports.assignment_id.
    Safe to run repeatedly; does not delete or rename anything."""
    migrated_asg = 0
    migrated_rep = 0
    # 1) Ensure each letter has an assignment linked by assignment_id
    letters = await db.assignment_letters.find({}, {"_id": 0}).to_list(5000)
    for letter in letters:
        account_ids = letter.get("account_ids") or ([letter["account_id"]] if letter.get("account_id") else [])
        if not account_ids:
            continue
        asg_id = letter.get("assignment_id")
        existing = await db.assignments.find_one({"id": asg_id}) if asg_id else None
        if existing:
            # ensure new-schema fields exist on legacy assignment docs
            patch = {}
            if "officer_id" not in existing and existing.get("petugas_id"):
                patch["officer_id"] = existing["petugas_id"]
            if "account_id" not in existing:
                patch["account_id"] = account_ids[0]
            if "power_of_attorney_id" not in existing and letter.get("surat_kuasa_id"):
                patch["power_of_attorney_id"] = letter["surat_kuasa_id"]
            if "status" not in existing:
                patch["status"] = LETTER_TO_ASSIGNMENT_STATUS.get(letter.get("status", "aktif"), "AKTIF")
            if "assignment_number" not in existing:
                patch["assignment_number"] = letter.get("nomor") or letter.get("document_number")
            if patch:
                patch["updated_at"] = now_iso()
                await db.assignments.update_one({"id": existing["id"]}, {"$set": patch})
            continue
        # no assignment: create one from letter (first account only -> 1:1)
        new_asg_id = asg_id or new_id()
        await db.assignments.insert_one({
            "id": new_asg_id, "company_id": letter["company_id"],
            "account_id": account_ids[0], "officer_id": letter.get("petugas_id"),
            "power_of_attorney_id": letter.get("surat_kuasa_id"), "client_id": letter.get("client_id"),
            "status": LETTER_TO_ASSIGNMENT_STATUS.get(letter.get("status", "aktif"), "AKTIF"),
            "valid_from": letter.get("tanggal"), "valid_until": letter.get("masa_berlaku"),
            "note": letter.get("catatan", ""),
            "assignment_number": letter.get("nomor") or letter.get("document_number"),
            "assignment_letter_id": letter["id"],
            "created_by": letter.get("generated_by", ""),
            "created_at": letter.get("created_at", now_iso()), "updated_at": now_iso(),
        })
        if letter.get("assignment_id") != new_asg_id:
            await db.assignment_letters.update_one({"id": letter["id"]}, {"$set": {"assignment_id": new_asg_id}})
        migrated_asg += 1
    # 2) Backfill field_reports.assignment_id from legacy assignment_letter_id
    reports = await db.field_reports.find({"assignment_id": {"$exists": False}}, {"_id": 0}).to_list(5000)
    for r in reports:
        if not r.get("assignment_letter_id"):
            continue
        letter = await db.assignment_letters.find_one({"id": r["assignment_letter_id"]}, {"_id": 0})
        if letter and letter.get("assignment_id"):
            await db.field_reports.update_one({"id": r["id"]}, {"$set": {"assignment_id": letter["assignment_id"]}})
            migrated_rep += 1
    if migrated_asg or migrated_rep:
        logger.info(f"Assignment migration: {migrated_asg} assignments, {migrated_rep} reports backfilled")


async def initialize_database():
    if transactions.ENABLED:
        hello = await db.command("hello")
        if not hello.get("setName") and hello.get("msg") != "isdbgrid":
            raise RuntimeError("DB_TRANSACTIONS requires a replica set or sharded MongoDB deployment")
    await db.users.create_index("email", unique=True)
    await db.revoked_tokens.create_index("id", unique=True)
    await db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier", unique=True)
    await db.login_attempts.create_index("expires_at", expireAfterSeconds=0)
    await db.upload_intents.create_index("id", unique=True)
    await db.upload_intents.create_index("created_at")
    await db.rate_limits.create_index("id", unique=True)
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.idempotency.create_index("id", unique=True)
    await db.idempotency.create_index("expires_at", expireAfterSeconds=0)
    for name in ("clients", "power_of_attorneys", "accounts", "assignments", "assignment_letters", "field_reports", "report_photos", "documents", "audit_logs", "companies"):
        await getattr(db, name).create_index("id", unique=True)
    await db.assignments.create_index([("company_id", 1), ("officer_id", 1), ("status", 1)])
    await db.assignment_letters.create_index([("status", 1), ("masa_berlaku", 1)])
    await db.field_reports.create_index([("company_id", 1), ("created_at", -1)])
    await db.report_photos.create_index("storage_path", unique=True)
    await db.documents.create_index([("company_id", 1), ("storage_path", 1)])
    await db.accounts.create_index("company_id")
    await db.field_reports.create_index("petugas_id")
    # Sparse key protects new submissions without requiring destructive legacy cleanup.
    await db.field_reports.create_index("submission_key", unique=True, sparse=True)
    await db.assignments.create_index("active_key", unique=True, sparse=True)
    await db.chat_messages.create_index("id", unique=True)
    await db.chat_messages.create_index([("company_id", 1), ("assignment_id", 1), ("sender_id", 1), ("client_message_id", 1)], unique=True)
    await db.chat_messages.create_index([("company_id", 1), ("assignment_id", 1), ("sequence", 1)], unique=True)
    await db.chat_messages.create_index([("company_id", 1), ("officer_id", 1), ("sender_id", 1)])
    await db.chat_reads.create_index([("company_id", 1), ("assignment_id", 1), ("user_id", 1)], unique=True)
    await db.assignments.create_index([("company_id", 1), ("officer_id", 1), ("chat_updated_at", -1)])
    if os.environ.get("SEED_DEMO_DATA", "false").lower() == "true":
        from seed import seed_all
        await seed_all(db)
    try:
        await migrate_assignments_non_destructive()
    except Exception as e:
        logger.error("Assignment migration failed: %s", type(e).__name__)
        if security.PRODUCTION:
            raise


async def reconcile_uploads():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    intents = await db.upload_intents.find({"created_at": {"$lt": cutoff}}, {"_id": 0}).to_list(50)
    for intent in intents:
        path = intent.get("storage_path", "")
        if not path.startswith(f"{APP_NAME}/companies/{intent['company_id']}/"):
            logger.warning("Invalid upload journal namespace; cleanup skipped")
            continue
        referenced = await db.report_photos.find_one({"storage_path": path}) or await db.documents.find_one({"storage_path": path, "company_id": intent["company_id"]}) or await db.chat_messages.find_one({"company_id": intent["company_id"], "attachments.storage_path": path})
        if not referenced:
            await run_in_threadpool(delete_object, path)
        await db.upload_intents.delete_one({"id": intent["id"]})


async def maintain_storage():
    while True:
        try:
            await run_in_threadpool(init_storage)
            app.state.storage_ready = True
            if app.state.database_ready:
                await reconcile_uploads()
        except Exception as exception:
            app.state.storage_ready = False
            logger.warning("Storage maintenance failed: %s", type(exception).__name__)
        await asyncio.sleep(60)


async def maintain_database_connection():
    last_expiry_check = None
    while True:
        try:
            await db.command("ping")
            if not app.state.database_ready:
                await initialize_database()
                app.state.database_ready = True
                logger.info("Database ready; application requests enabled")
            current = datetime.now(timezone.utc)
            if last_expiry_check is None or (current - last_expiry_check).total_seconds() >= 60:
                today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
                expired = await db.assignment_letters.find({"status": "aktif", "masa_berlaku": {"$type": "string", "$lt": today, "$ne": ""}}, {"_id": 0}).to_list(200)
                for letter in expired:
                    try:
                        await update_st_status(letter["id"], StatusUpdate(status="kedaluwarsa"), None, {"id": "system", "name": "Sistem", "company_id": letter["company_id"], "role": "admin"})
                    except HTTPException as exception:
                        logger.info("Expiry reconciliation skipped changed letter %s (%s)", letter["id"], exception.status_code)
                last_expiry_check = current
        except Exception as exception:
            app.state.database_ready = False
            logger.warning("Database not ready; retrying in 15 seconds (%s)", type(exception).__name__)
        await asyncio.sleep(15)


@app.on_event("startup")
async def startup():
    app.state.database_ready = False
    app.state.database_task = asyncio.create_task(maintain_database_connection())
    try:
        await run_in_threadpool(init_storage)
        app.state.storage_ready = True
        logger.info("Object storage initialized")
    except Exception as exception:
        app.state.storage_ready = False
        logger.warning("Object storage initialization failed: %s", type(exception).__name__)
    app.state.storage_task = asyncio.create_task(maintain_storage())

@app.on_event("shutdown")
async def shutdown():
    for name in ("database_task", "storage_task"):
        task = getattr(app.state, name, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    app.state.database_ready = False
    client.close()
