"""Cache JSON mutation results in the same transaction as business writes."""
import hashlib
import inspect
import json
import re
from functools import wraps
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException


def decorator(database_getter, runner):
    def decorate(function):
        signature = inspect.signature(function)
        @wraps(function)
        async def execute(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs).arguments
            request, user = bound.get("request"), bound.get("user")
            supplied = request.headers.get("Idempotency-Key") if request is not None else None
            if not supplied:
                return await runner(lambda: function(*args, **kwargs))
            if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", supplied):
                raise HTTPException(status_code=400, detail="Idempotency-Key tidak valid")
            if not user:
                raise HTTPException(status_code=400, detail="Idempotency memerlukan sesi pengguna")
            data = bound.get("data")
            content = json.dumps(data.model_dump(mode="json") if hasattr(data, "model_dump") else {}, sort_keys=True, separators=(",", ":"))
            fingerprint = hashlib.sha256(content.encode()).hexdigest()
            key = hashlib.sha256(f"{user['company_id']}:{user['id']}:{request.method}:{request.url.path}:{supplied}".encode()).hexdigest()
            async def operation():
                db = database_getter()
                existing = await db.idempotency.find_one({"id": key, "company_id": user["company_id"]})
                if existing:
                    if existing["fingerprint"] != fingerprint:
                        raise HTTPException(status_code=409, detail="Kunci permintaan sudah dipakai untuk data berbeda")
                    return existing["response"]
                result = await function(*args, **kwargs)
                await db.idempotency.insert_one({"id": key, "company_id": user["company_id"], "fingerprint": fingerprint, "response": result, "expires_at": datetime.now(timezone.utc)+timedelta(days=1)})
                return result
            return await runner(operation)
        return execute
    return decorate
