import os
import requests
import mimetypes
import tempfile
from pathlib import Path
from functools import wraps


class StorageUnavailable(RuntimeError):
    pass


def storage_errors(function):
    @wraps(function)
    def execute(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except FileNotFoundError:
            raise
        except (OSError, requests.RequestException) as error:
            raise StorageUnavailable(type(error).__name__) from error
        except Exception as error:
            if error.__class__.__module__.startswith("botocore"):
                raise StorageUnavailable(type(error).__name__) from error
            raise
    return execute


_s3 = None


def s3_client():
    global _s3
    if _s3 is None:
        import boto3
        from botocore.config import Config
        _s3 = boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None, region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2, "mode": "standard"}, s3={"addressing_style": os.environ.get("S3_ADDRESSING_STYLE", "auto")}))
    return _s3

STORAGE_BACKEND = os.environ.get("FILE_STORAGE_BACKEND", "remote").lower()
LOCAL_STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR") or Path(__file__).resolve().parent.parent / ".local" / "uploads").resolve()


def local_path(path: str) -> Path:
    if not path or "\\" in path or any(part in {"", ".", ".."} for part in path.split("/")) or ":" in path:
        raise ValueError("Invalid storage path")
    target = (LOCAL_STORAGE_DIR / path).resolve()
    if not target.is_relative_to(LOCAL_STORAGE_DIR) or target == LOCAL_STORAGE_DIR:
        raise ValueError("Invalid storage path")
    return target

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "fieldcollector"

_storage_key = None


@storage_errors
def init_storage(force: bool = False):
    global _storage_key
    if STORAGE_BACKEND == "local":
        LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=LOCAL_STORAGE_DIR) as probe:
            probe.write(b"ready")
            probe.flush()
        return "local"
    if STORAGE_BACKEND == "s3":
        bucket = os.environ.get("S3_BUCKET")
        if not bucket:
            raise ValueError("S3_BUCKET is required")
        s3_client().head_bucket(Bucket=bucket)
        return "s3"
    if STORAGE_BACKEND != "remote":
        raise ValueError("FILE_STORAGE_BACKEND must be local, s3 or remote")
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


@storage_errors
def put_object(path: str, data: bytes, content_type: str) -> dict:
    if STORAGE_BACKEND == "s3":
        options = {"ServerSideEncryption": os.environ.get("S3_ENCRYPTION", "AES256")}
        s3_client().put_object(Bucket=os.environ["S3_BUCKET"], Key=path, Body=data, ContentType=content_type, **options)
        return {"path": path}
    if STORAGE_BACKEND == "local":
        target = local_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            os.replace(temporary, target)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return {"path": path}
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


@storage_errors
def get_object(path: str):
    if STORAGE_BACKEND == "s3":
        try:
            response = s3_client().get_object(Bucket=os.environ["S3_BUCKET"], Key=path)
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise FileNotFoundError(path) from error
            raise
        body = response["Body"]
        try:
            return body.read(), response.get("ContentType", "application/octet-stream")
        finally:
            if hasattr(body, "close"):
                body.close()
    if STORAGE_BACKEND == "local":
        return local_path(path).read_bytes(), mimetypes.guess_type(path)[0] or "application/octet-stream"
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


@storage_errors
def delete_object(path: str):
    if STORAGE_BACKEND == "local":
        local_path(path).unlink(missing_ok=True)
    elif STORAGE_BACKEND == "s3":
        s3_client().delete_object(Bucket=os.environ["S3_BUCKET"], Key=path)
    else:
        raise StorageUnavailable("Remote provider deletion is not configured")
