"""Assignment conversations: tenant/owner authorization and durable retry keys."""
import hashlib
import io
import json
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from fastapi import Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from database import ReturnDocument
from pypdf.errors import PdfReadError
from starlette.concurrency import run_in_threadpool

MAX_ATTACHMENT = 10 * 1024 * 1024
DOCUMENT_TYPES = {
    ".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=100000)


class ReadInput(BaseModel):
    sequence: int = Field(ge=0)


def safe_filename(value):
    value = unicodedata.normalize("NFKC", value or "lampiran").replace("\\", "/").split("/")[-1]
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))
    return value[:160] or "lampiran"


def validate_attachment(content, filename, runtime):
    """Check actual file content; images are normalized and lose hidden metadata."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in {".jpg", ".jpeg", ".png", ".webp"}:
        if len(content) > runtime.MAX_FILE_SIZE:
            raise HTTPException(413, "Foto maksimal 8 MB")
        runtime.verified_image_format(content, {"JPEG", "PNG", "WEBP"}, 20_000_000)
        with runtime.Image.open(io.BytesIO(content)) as image:
            image = runtime.ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2560, 2560))
            out = io.BytesIO(); image.save(out, "JPEG", quality=90)
        return out.getvalue(), "image/jpeg", ".jpg", "image"
    if extension not in DOCUMENT_TYPES:
        raise HTTPException(400, "Gunakan JPG/PNG/WebP, PDF, TXT, CSV, DOCX, XLSX atau PPTX")
    if extension == ".pdf":
        try: runtime.validate_pdf(content)
        except (ValueError, PdfReadError, KeyError, TypeError, RecursionError):
            raise HTTPException(400, "PDF tidak valid atau mengandung konten aktif")
    elif extension in {".txt", ".csv"}:
        try:
            text = content.decode("utf-8-sig")
            if "\x00" in text: raise ValueError()
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400, "Dokumen teks harus berformat UTF-8")
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 40 * 1024 * 1024:
                    raise ValueError()
                prefix = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}[extension]
                names = {e.filename for e in entries}
                if "[Content_Types].xml" not in names or not any(n.startswith(prefix) for n in names):
                    raise ValueError()
                if b"macroenabled" in archive.read("[Content_Types].xml").lower(): raise ValueError()
                for entry in entries:
                    name = entry.filename.lower()
                    if entry.flag_bits & 1 or name.startswith("/") or ".." in name.split("/") or "vbaproject" in name or "/embeddings/" in name or "/activex/" in name:
                        raise ValueError()
                if archive.testzip() is not None: raise ValueError()
        except (zipfile.BadZipFile, RuntimeError, ValueError, OSError, NotImplementedError):
            raise HTTPException(400, "Dokumen Office tidak valid atau mengandung macro/objek tertanam")
    return content, DOCUMENT_TYPES[extension], extension, "document"


def register(router, runtime):
    async def assignment(assignment_id, user):
        query = {"id": assignment_id, "company_id": user["company_id"]}
        if user["role"] == "petugas": query["officer_id"] = user["id"]
        elif user["role"] != "admin": raise HTTPException(403, "Akses chat tidak diizinkan")
        record = await runtime.db.assignments.find_one(query, {"_id": 0})
        if not record: raise HTTPException(404, "Percakapan tidak ditemukan")
        return record

    def public_message(record):
        result = {k: v for k, v in record.items() if k not in {"_id", "fingerprint", "company_id", "officer_id"}}
        result["attachments"] = [{k: v for k, v in a.items() if k != "storage_path"} for a in record.get("attachments", [])]
        return result

    async def context(record):
        letter = await runtime.db.assignment_letters.find_one({"assignment_id": record["id"], "company_id": record["company_id"]}, {"document_snapshot": 1, "snapshot_data": 1}) or {}
        snapshot = letter.get("document_snapshot") or letter.get("snapshot_data") or {}
        account = (snapshot.get("accounts") or [{}])[0]
        return {"account_name": account.get("debtor_name", ""), "contract_number": account.get("contract_number", ""), "license_plate": account.get("license_plate", ""), "officer_name": snapshot.get("officer", {}).get("name", "Petugas")}

    async def unread(record, user):
        read = await runtime.db.chat_reads.find_one({"company_id": user["company_id"], "assignment_id": record["id"], "user_id": user["id"]})
        return await runtime.db.chat_messages.count_documents({"company_id": user["company_id"], "assignment_id": record["id"], "sender_id": {"$ne": user["id"]}, "sequence": {"$gt": (read or {}).get("sequence", 0)}})

    @router.get("/chat/unread")
    async def unread_total(user: dict = Depends(runtime.get_current_user)):
        if user["role"] not in {"admin", "petugas"}: raise HTTPException(403, "Akses chat tidak diizinkan")
        return {"count": await runtime.db.unread_messages(user)}

    @router.get("/chat")
    async def inbox(page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=100), user: dict = Depends(runtime.get_current_user)):
        query = {"company_id": user["company_id"], "chat_sequence": {"$gt": 0}}
        if user["role"] == "petugas": query["officer_id"] = user["id"]
        elif user["role"] != "admin": raise HTTPException(403, "Akses chat tidak diizinkan")
        records = await runtime.db.assignments.find(query, {"_id": 0}).sort([("chat_updated_at", -1), ("id", 1)]).skip((page - 1) * limit).to_list(limit + 1)
        items = []
        for record in records[:limit]:
            items.append({"assignment_id": record["id"], "number": record.get("assignment_number", ""), "status": record["status"], "last_message": record.get("chat_preview", ""), "updated_at": record.get("chat_updated_at"), "unread": await unread(record, user), **await context(record)})
        return {"items": items, "next_page": page + 1 if len(records) > limit else None}

    @router.get("/chat/{assignment_id}")
    async def messages(assignment_id: str, after: int = Query(0, ge=0), before: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=100), user: dict = Depends(runtime.get_current_user)):
        record = await assignment(assignment_id, user)
        query = {"company_id": user["company_id"], "assignment_id": assignment_id}
        if before is not None: query["sequence"] = {"$lt": before}
        elif after: query["sequence"] = {"$gt": after}
        ascending = after > 0 and before is None
        rows = await runtime.db.chat_messages.find(query, {"_id": 0}).sort("sequence", 1 if ascending else -1).to_list(limit + 1)
        more = len(rows) > limit
        rows = rows[:limit]
        if not ascending: rows.reverse()
        return {"assignment": {"id": record["id"], "number": record.get("assignment_number", ""), "status": record["status"], "read_only": record["status"] != runtime.ASSIGNMENT_ACTIVE, **await context(record)}, "messages": [public_message(row) for row in rows], "has_more": more, "unread": await unread(record, user)}

    @router.post("/chat/{assignment_id}/read")
    async def mark_read(assignment_id: str, data: ReadInput, user: dict = Depends(runtime.get_current_user)):
        record = await assignment(assignment_id, user)
        sequence = min(data.sequence, record.get("chat_sequence", 0))
        await runtime.db.chat_reads.update_one({"company_id": user["company_id"], "assignment_id": assignment_id, "user_id": user["id"]}, {"$max": {"sequence": sequence}}, upsert=True)
        return {"sequence": sequence}

    @router.post("/chat/{assignment_id}/messages")
    async def send_message(assignment_id: str, client_message_id: str = Form(...), text: str = Form(""), location: str = Form(""), files: list[UploadFile] = File(default=[]), user: dict = Depends(runtime.get_current_user)):
        await assignment(assignment_id, user)
        try: client_id = str(uuid.UUID(client_message_id))
        except ValueError: raise HTTPException(400, "ID pengiriman tidak valid")
        text = text.strip()
        if len(text) > 4000: raise HTTPException(400, "Pesan maksimal 4.000 karakter")
        try: point = Location.model_validate_json(location).model_dump() if location else None
        except ValidationError: raise HTTPException(400, "Lokasi tidak valid")
        if len(files) > 4: raise HTTPException(400, "Maksimal 4 lampiran per pesan")
        if not text and not files and not point: raise HTTPException(400, "Pesan tidak boleh kosong")
        prepared = []; signatures = []
        for upload in files:
            content = await upload.read(MAX_ATTACHMENT + 1)
            if not content or len(content) > MAX_ATTACHMENT: raise HTTPException(413, "Lampiran maksimal 10 MB dan tidak boleh kosong")
            filename = safe_filename(upload.filename)
            signatures.append({"name": filename, "sha256": hashlib.sha256(content).hexdigest()})
            content, mime, extension, kind = await run_in_threadpool(validate_attachment, content, filename, runtime)
            if kind == "image": filename = filename.rsplit(".", 1)[0] + extension
            prepared.append((content, mime, extension, kind, filename))
        fingerprint = hashlib.sha256(json.dumps({"text": text, "location": point, "files": signatures}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = {"company_id": user["company_id"], "assignment_id": assignment_id, "sender_id": user["id"], "client_message_id": client_id}
        def cached(existing):
            if existing["fingerprint"] != fingerprint: raise HTTPException(409, "ID pengiriman sudah digunakan untuk pesan berbeda")
            return public_message(existing)
        existing = await runtime.db.chat_messages.find_one(key)
        if existing: return cached(existing)
        moment = datetime.now(timezone.utc)
        bucket = f"chat:{user['company_id']}:{user['id']}:{int(moment.timestamp()) // 60}"
        rate = await runtime.db.rate_limits.find_one_and_update({"id": bucket}, {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": moment + timedelta(minutes=2)}}, upsert=True, return_document=ReturnDocument.AFTER)
        if rate["count"] > 30: raise HTTPException(429, "Terlalu banyak pesan; coba lagi dalam satu menit")
        active = await assignment(assignment_id, user)
        if active["status"] != runtime.ASSIGNMENT_ACTIVE: raise HTTPException(409, "Tugas sudah ditutup; chat hanya dapat dibaca")
        attachments = []
        for content, mime, extension, kind, filename in prepared:
            identity = runtime.new_id()
            path = f"{runtime.APP_NAME}/companies/{user['company_id']}/chat/{identity}{extension}"
            await runtime.db.upload_intents.insert_one({"id": path, "storage_path": path, "company_id": user["company_id"], "created_at": runtime.datetime.now(runtime.timezone.utc)})
            await run_in_threadpool(runtime.put_object, path, content, mime)
            attachments.append({"id": identity, "name": filename, "size": len(content), "content_type": mime, "kind": kind, "storage_path": path, "url": f"/api/chat/{assignment_id}/attachments/{identity}"})
        async def commit():
            existing = await runtime.db.chat_messages.find_one(key)
            if existing: return cached(existing)
            current = await assignment(assignment_id, user)
            if current["status"] != runtime.ASSIGNMENT_ACTIVE: raise HTTPException(409, "Tugas sudah ditutup; chat hanya dapat dibaca")
            preview = text[:160] or ("📍 Lokasi" if point else "📎 " + attachments[0]["name"])
            changed = await runtime.db.assignments.find_one_and_update({"id": assignment_id, "company_id": user["company_id"], "status": runtime.ASSIGNMENT_ACTIVE}, {"$inc": {"chat_sequence": 1}, "$set": {"chat_updated_at": runtime.now_iso(), "chat_preview": preview}}, return_document=ReturnDocument.AFTER)
            if not changed: raise HTTPException(409, "Tugas sudah ditutup; chat hanya dapat dibaca")
            message = {**key, "id": runtime.new_id(), "sequence": changed["chat_sequence"], "officer_id": current["officer_id"], "sender_name": user["name"], "sender_role": user["role"], "text": text, "location": point, "attachments": attachments, "fingerprint": fingerprint, "created_at": runtime.now_iso()}
            await runtime.db.chat_messages.insert_one(message)
            for attachment in attachments:
                await runtime.db.upload_intents.delete_one({"id": attachment["storage_path"], "company_id": user["company_id"]})
            await runtime.log_audit(user, "Mengirim pesan chat", "assignment", assignment_id)
            return public_message(message)
        return await runtime.transactions.run(runtime.client, commit)

    @router.get("/chat/{assignment_id}/attachments/{attachment_id}")
    async def attachment(assignment_id: str, attachment_id: str, user: dict = Depends(runtime.get_current_user)):
        await assignment(assignment_id, user)
        record = await runtime.db.chat_messages.find_one({"company_id": user["company_id"], "assignment_id": assignment_id, "attachments.id": attachment_id})
        if not record: raise HTTPException(404, "Lampiran tidak ditemukan")
        item = next(a for a in record["attachments"] if a["id"] == attachment_id)
        try: content, _ = await run_in_threadpool(runtime.get_object, item["storage_path"])
        except FileNotFoundError: raise HTTPException(404, "Lampiran tidak ditemukan di penyimpanan")
        disposition = "inline" if item["kind"] == "image" else "attachment"
        filename = quote(item["name"], safe="")
        return Response(content=content, media_type=item["content_type"], headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": f"{disposition}; filename=lampiran; filename*=UTF-8''{filename}"})
