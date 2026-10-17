"""Admin-authored field evidence and one payment per assignment/team."""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from fastapi import Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from assignment_team import member_ids

WAITING = "MENUNGGU_PEMBAYARAN"
PAID = "SELESAI"
ELIGIBLE = ["AKTIF", "SELESAI", "KEDALUWARSA"]


def amount(value):
    try:
        parsed = Decimal(value)
        if not parsed.is_finite() or parsed <= 0 or parsed > Decimal("999999999999.99") or parsed.as_tuple().exponent < -2:
            raise ValueError()
        return format(parsed, ".2f")
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(400, "Nominal pembayaran tim harus lebih dari nol, maksimal 999999999999.99 dan dua angka desimal")


def request_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "ID pengiriman tidak valid. Muat ulang formulir.")


async def validate_upload(upload, runtime, payment=False):
    content = await upload.read(runtime.MAX_FILE_SIZE + 1)
    if not content or len(content) > runtime.MAX_FILE_SIZE:
        raise HTTPException(400, "Setiap file harus berisi data dan maksimal 8 MB")
    if payment and upload.content_type == "application/pdf":
        try:
            await run_in_threadpool(runtime.validate_pdf, content)
        except Exception:
            raise HTTPException(400, "PDF bukti pembayaran tidak valid atau mengandung konten aktif")
        extension, mime = "pdf", "application/pdf"
    else:
        if upload.content_type not in runtime.ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, "Gunakan gambar JPG, PNG, WEBP; bukti pembayaran juga dapat berupa PDF")
        actual = await run_in_threadpool(runtime.verified_image_format, content, {"PNG", "JPEG", "WEBP"}, 20_000_000)
        extension, mime = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg"), "WEBP": ("webp", "image/webp")}[actual]
    return {"content": content, "extension": extension, "content_type": mime, "name": (upload.filename or "bukti").replace("\\", "/").split("/")[-1][:160], "kind": "payment" if payment else "report"}


def fingerprint(values, uploads):
    return hashlib.sha256(json.dumps({"values": values, "uploads": [{"kind": f["kind"], "name": f["name"], "sha256": hashlib.sha256(f["content"]).hexdigest()} for f in uploads]}, sort_keys=True).encode()).hexdigest()


def register(router, runtime):
    async def store_file(prepared, report_id, user):
        identity = runtime.new_id()
        path = f"{runtime.APP_NAME}/companies/{user['company_id']}/reports/{report_id}/{identity}.{prepared['extension']}"
        await runtime.db.upload_intents.insert_one({"id": path, "company_id": user["company_id"], "storage_path": path, "created_at": datetime.now(timezone.utc)})
        await run_in_threadpool(runtime.put_object, path, prepared["content"], prepared["content_type"])
        return {"id": identity, "report_id": report_id, "storage_path": path, "url": "/api/files/"+path, "kind": prepared["kind"], "name": prepared["name"], "content_type": prepared["content_type"], "size": len(prepared["content"]), "created_at": runtime.now_iso()}

    async def persist_files(files, user):
        for item in files:
            await runtime.db.report_photos.insert_one(item)
            await runtime.db.upload_intents.delete_one({"id": item["storage_path"], "company_id": user["company_id"]})

    def public_file(item):
        return {key: value for key, value in item.items() if key not in {"storage_path", "report_id"}}

    @router.get("/laporan-options")
    async def options(page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=500), user: dict = Depends(runtime.admin_required)):
        rows = await runtime.db.reportable_assignments(user["company_id"], ELIGIBLE, page, limit)
        items = []
        for row in rows[:limit]:
            if await runtime.db.field_reports.find_one({"company_id": user["company_id"], "assignment_id": row["id"]}):
                continue
            letter = await runtime.db.assignment_letters.find_one({"company_id": user["company_id"], "assignment_id": row["id"]}) or {}
            snapshot = letter.get("document_snapshot") or {}
            account = (snapshot.get("accounts") or [{}])[0]
            if not account:
                current = await runtime.db.accounts.find_one({"company_id": user["company_id"], "id": row["account_id"]}) or {}
                account = {"debtor_name": current.get("nama_debitur", ""), "license_plate": current.get("nomor_polisi", "")}
            items.append({"assignment_id": row["id"], "number": letter.get("document_number") or letter.get("nomor") or row.get("assignment_number", ""), "debtor_name": account.get("debtor_name", ""), "license_plate": account.get("license_plate", ""), "officer_count": len(member_ids(row))})
        return {"items": items, "next_page": page+1 if len(rows)>limit else None}

    @router.post("/laporan")
    async def create(request: Request, assignment_id: str = Form(...), client_report_id: str = Form(""), payment_amount: str = Form(""), catatan: str = Form(""), status: str = Form("LAINNYA"), photos: list[UploadFile] = File(default=[]), payment_proof: UploadFile | None = File(None), user: dict = Depends(runtime.admin_required)):
        key = request_id(client_report_id)
        nominal = amount(payment_amount)
        if len(catatan) > 4000 or status not in runtime.ACCOUNT_STATUS_MAP:
            raise HTTPException(400, "Catatan maksimal 4.000 karakter dan hasil laporan harus valid")
        assignment = await runtime.db.assignments.find_one({"id": assignment_id, "company_id": user["company_id"]})
        if not assignment:
            raise HTTPException(404, "Penugasan tidak ditemukan")
        if assignment.get("status") not in ELIGIBLE:
            raise HTTPException(409, "Penugasan dibatalkan atau tidak tersedia untuk laporan")
        if not 1 <= len(photos) <= 10:
            raise HTTPException(400, "Unggah minimal 1 dan maksimal 10 gambar bukti laporan")
        prepared = [await validate_upload(photo, runtime) for photo in photos]
        if payment_proof and payment_proof.filename:
            prepared.append(await validate_upload(payment_proof, runtime, payment=True))
        if sum(len(item["content"]) for item in prepared) > 40*1024*1024:
            raise HTTPException(400, "Total bukti laporan dan pembayaran maksimal 40 MB")
        digest = fingerprint([assignment_id, nominal, catatan, status], prepared)
        async def cached(existing):
            if existing.get("client_report_id") == key and existing.get("submission_fingerprint") == digest:
                photos = await runtime.db.report_photos.find({"report_id": existing["id"], "kind": {"$ne": "payment"}}, {"_id": 0}).to_list(10)
                return {**existing, "photos": photos}
            raise HTTPException(409, "Laporan untuk penugasan ini sudah dibuat. Buka laporan yang ada.")
        existing = await runtime.db.field_reports.find_one({"company_id": user["company_id"], "assignment_id": assignment_id})
        if existing:
            return await cached(existing)
        letter = await runtime.db.assignment_letters.find_one({"company_id": user["company_id"], "assignment_id": assignment_id})
        ids = member_ids(assignment)
        if not letter or not ids:
            raise HTTPException(409, "Data surat atau tim penugasan belum lengkap")
        report_id = runtime.new_id()
        saved = [await store_file(item, report_id, user) for item in prepared]
        proof = next((public_file(item) for item in saved if item["kind"] == "payment"), None)
        state = PAID if proof else WAITING
        snapshot = letter.get("document_snapshot") or {}
        names = [person.get("name", "") for person in snapshot.get("officers", [])]
        if not names:
            for identity in ids:
                person = await runtime.db.users.find_one({"id": identity, "company_id": user["company_id"]}, {"name": 1}) or {}
                names.append(person.get("name", "-"))
        record = {"id": report_id, "company_id": user["company_id"], "assignment_id": assignment_id, "submission_key": assignment_id, "assignment_letter_id": letter["id"], "account_id": assignment["account_id"], "petugas_id": ids[0], "petugas_ids": ids, "team_names": names, "created_by": user["id"], "created_by_name": user["name"], "created_role": user["role"], "client_report_id": key, "submission_fingerprint": digest, "payment_scope": "TEAM", "payment_amount": nominal, "payment_status": state, "report_status": state, "status": status, "catatan": catatan.strip(), "latitude": None, "longitude": None, "catatan_admin": "", "reviewed": False, "created_at": runtime.now_iso(), "updated_at": runtime.now_iso()}
        if proof:
            record.update(payment_proof=proof, payment_recorded_at=runtime.now_iso(), payment_recorded_by=user["id"])
        async def commit():
            current = await runtime.db.assignments.find_one_and_update({"id": assignment_id, "company_id": user["company_id"], "status": {"$in": ELIGIBLE}}, {"$inc": {"report_version": 1}}, return_document=True)
            if not current:
                raise HTTPException(409, "Penugasan sudah berubah atau dibatalkan")
            existing = await runtime.db.field_reports.find_one({"company_id": user["company_id"], "assignment_id": assignment_id})
            if existing:
                return await cached(existing)
            account = await runtime.db.accounts.find_one({"id": assignment["account_id"], "company_id": user["company_id"]}, {"_id": 0})
            if not account:
                raise HTTPException(409, "Unit penugasan tidak ditemukan")
            record["account_snapshot"] = account
            await runtime.db.field_reports.insert_one(dict(record))
            await persist_files(saved, user)
            if status != "LAINNYA":
                await runtime.db.accounts.update_one({"id": account["id"], "company_id": user["company_id"], "active_assignment_id": assignment_id}, {"$set": {"status": runtime.ACCOUNT_STATUS_MAP[status], "updated_at": runtime.now_iso()}})
            await runtime.log_audit(user, "Membuat laporan lapangan dan pembayaran tim", "field_report", report_id, request)
            if proof: await runtime.whatsapp.enqueue(runtime, "payment", record, user)
            return {**record, "photos": [public_file(item) for item in saved if item["kind"] == "report"]}
        try:
            return await runtime.transactions.run(runtime.client, commit)
        except runtime.DuplicateKeyError:
            existing = await runtime.db.field_reports.find_one({"company_id": user["company_id"], "assignment_id": assignment_id})
            if existing:
                return await cached(existing)
            raise HTTPException(409, "Laporan untuk penugasan ini sudah dibuat. Muat ulang daftar laporan.")

    @router.post("/laporan/{rid}/payment")
    async def pay(rid: str, request: Request, payment_request_id: str = Form(""), payment_amount: str = Form(""), file: UploadFile = File(...), user: dict = Depends(runtime.admin_required)):
        key = request_id(payment_request_id)
        report = await runtime.db.field_reports.find_one({"id": rid, "company_id": user["company_id"]})
        if not report:
            raise HTTPException(404, "Laporan tidak ditemukan")
        nominal = amount(report.get("payment_amount") or payment_amount)
        if payment_amount and amount(payment_amount) != nominal:
            raise HTTPException(409, "Nominal pembayaran harus sesuai laporan")
        prepared = await validate_upload(file, runtime, payment=True)
        digest = fingerprint([rid, nominal], [prepared])
        def cached(existing):
            if existing.get("payment_request_id") == key and existing.get("payment_fingerprint") == digest:
                return existing
            raise HTTPException(409, "Bukti pembayaran sudah dicatat dan tidak dapat ditimpa")
        if report.get("payment_proof"):
            return cached(report)
        saved = await store_file(prepared, rid, user)
        async def commit():
            current = await runtime.db.field_reports.find_one_and_update({"id": rid, "company_id": user["company_id"]}, {"$inc": {"payment_version": 1}}, return_document=True)
            if not current:
                raise HTTPException(404, "Laporan tidak ditemukan")
            if current.get("payment_proof"):
                return cached(current)
            update = {"payment_amount": nominal, "payment_scope": "TEAM", "payment_status": PAID, "report_status": PAID, "payment_proof": public_file(saved), "payment_request_id": key, "payment_fingerprint": digest, "payment_recorded_at": runtime.now_iso(), "payment_recorded_by": user["id"], "updated_at": runtime.now_iso()}
            await runtime.db.field_reports.update_one({"id": rid, "company_id": user["company_id"]}, {"$set": update})
            await persist_files([saved], user)
            await runtime.log_audit(user, "Mengunggah bukti pembayaran tim", "field_report", rid, request)
            await runtime.whatsapp.enqueue(runtime, "payment", {**current, **update}, user)
            return {**current, **update}
        return await runtime.transactions.run(runtime.client, commit)
