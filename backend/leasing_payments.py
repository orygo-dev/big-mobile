"""Leasing payments stored with their private evidence in the document ledger."""
import uuid
from datetime import datetime, timezone
from fastapi import Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from admin_reports import amount, request_id, validate_upload, fingerprint

KIND = "leasing_payment"


def public(record):
    return {key: value for key, value in record.items() if key not in {"_id", "storage_path", "fingerprint", "company_id", "kind"}}


def register(router, runtime):
    @router.get("/leasing-payments")
    async def listing(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100), user: dict = Depends(runtime.admin_required)):
        rows = await runtime.db.documents.find({"company_id": user["company_id"], "kind": KIND}, {"_id": 0}).sort([("created_at", -1), ("id", -1)]).skip((page-1)*limit).limit(limit+1).to_list(limit+1)
        return {"items": [public(row) for row in rows[:limit]], "next_page": page+1 if len(rows)>limit else None}

    @router.post("/leasing-payments")
    async def create(request: Request, client_id: str = Form(...), payment_amount: str = Form(...), payment_request_id: str = Form(...), file: UploadFile = File(...), user: dict = Depends(runtime.admin_required)):
        key = request_id(payment_request_id)
        try:
            nominal = amount(payment_amount)
        except HTTPException:
            raise HTTPException(400, "Jumlah pembayaran harus lebih dari nol, maksimal 999999999999.99 dan dua angka desimal")
        prepared = await validate_upload(file, runtime, payment=True)
        digest = fingerprint([client_id, nominal], [prepared])
        identity = str(uuid.uuid5(uuid.NAMESPACE_URL, f"leasing-payment:{user['company_id']}:{key}"))
        scope = {"id": identity, "company_id": user["company_id"], "kind": KIND}

        def cached(record):
            if record.get("fingerprint") != digest:
                raise HTTPException(409, "Pengiriman ini sudah digunakan untuk pembayaran berbeda. Muat ulang formulir.")
            return public(record)

        existing = await runtime.db.documents.find_one(scope)
        if existing:
            return cached(existing)
        leasing_scope = {"id": client_id, "company_id": user["company_id"]}
        leasing = await runtime.db.clients.find_one(leasing_scope)
        if not leasing:
            raise HTTPException(404, "Leasing tidak ditemukan")
        path = f"{runtime.APP_NAME}/companies/{user['company_id']}/leasing-payments/{identity}/{runtime.new_id()}.{prepared['extension']}"
        await runtime.db.upload_intents.insert_one({"id": path, "storage_path": path, "company_id": user["company_id"], "created_at": datetime.now(timezone.utc)})
        await run_in_threadpool(runtime.put_object, path, prepared["content"], prepared["content_type"])

        async def commit():
            locked = await runtime.db.clients.find_one_and_update(leasing_scope, {"$inc": {"relation_version": 1}}, return_document=True)
            if not locked:
                raise HTTPException(404, "Leasing tidak ditemukan")
            existing = await runtime.db.documents.find_one(scope)
            if existing:
                return cached(existing)
            record = {**scope, "client_id": client_id, "leasing_name": locked.get("nama_perusahaan") or leasing["nama_perusahaan"], "payment_amount": nominal, "created_at": runtime.now_iso(), "created_by": user["id"], "filename": prepared["name"], "content_type": prepared["content_type"], "storage_path": path, "url": "/api/files/"+path, "fingerprint": digest}
            await runtime.db.documents.insert_one(dict(record))
            await runtime.db.upload_intents.delete_one({"id": path, "company_id": user["company_id"]})
            await runtime.log_audit(user, "Mencatat pembayaran leasing", KIND, identity, request)
            return public(record)

        return await runtime.transactions.run(runtime.client, commit)
