import os
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs, unquote
import jwt

PRODUCTION = os.environ.get("APP_ENV", "development") == "production"
TOKEN_HOURS = int(os.environ.get("ACCESS_TOKEN_HOURS", "8"))
COOKIE_NAME = "fc_session"
ISSUER = "big-mobile-api"
AUDIENCE = "big-mobile"


def validate_configuration():
    if not 1 <= TOKEN_HOURS <= 24:
        raise RuntimeError("ACCESS_TOKEN_HOURS must be between 1 and 24")
    if not PRODUCTION:
        return
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32 or any(value in secret.lower() for value in ("replace-with", "demo", "test-secret", "changeme")):
        raise RuntimeError("Production requires a random JWT_SECRET of at least 32 characters")
    url = urlparse(os.environ.get("APP_BASE_URL", ""))
    if url.scheme != "https" or not url.hostname:
        raise RuntimeError("Production APP_BASE_URL must use HTTPS")
    if os.environ.get("DB_TRANSACTIONS", "true").lower() != "true":
        raise RuntimeError("Production requires DB_TRANSACTIONS=true")
    if os.environ.get("SEED_DEMO_DATA", "false").lower() != "false":
        raise RuntimeError("Production demo seed must be disabled")
    if os.environ.get("FILE_STORAGE_BACKEND", "remote") not in {"local", "s3"}:
        raise RuntimeError("Production requires configured local or S3 storage")
    origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()]
    if not origins or "*" in origins or any(urlparse(origin).scheme != "https" for origin in origins):
        raise RuntimeError("Production CORS origins must be explicit HTTPS origins")
    mysql = urlparse(os.environ.get("MYSQL_URL", ""))
    options = parse_qs(mysql.query)
    if mysql.scheme != "mysql" or not mysql.hostname or not mysql.username or not mysql.password:
        raise RuntimeError("Production MySQL authentication is required")
    if unquote(mysql.username).lower() == "root":
        raise RuntimeError("Production MySQL must use a dedicated application user")
    if mysql.hostname not in {"localhost", "127.0.0.1", "::1"} and not options.get("ssl_ca"):
        raise RuntimeError("Remote MySQL requires a verified TLS CA certificate")
    if any(name not in {"ssl_ca"} for name in options):
        raise RuntimeError("Unsupported MySQL connection option")
    monitor = os.environ.get("MONITOR_TOKEN", "")
    if len(monitor) < 32 or "replace-with" in monitor or monitor == secret:
        raise RuntimeError("Production requires a separate random MONITOR_TOKEN")
    if os.environ.get("S3_ENDPOINT_URL") and urlparse(os.environ["S3_ENDPOINT_URL"]).scheme != "https":
        raise RuntimeError("Production S3 endpoint must use HTTPS")


def decode_access_token(token, secret):
    return jwt.decode(token, secret, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER, options={"require": ["exp", "iat", "jti", "sub", "type"]})


def rate_key(ip, email):
    return hashlib.sha256(f"{ip}:{email}".encode()).hexdigest()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {"time": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            # Exception class is useful without echoing credentials/URIs/body.
            result["exception"] = record.exc_info[0].__name__
        return json.dumps(result, ensure_ascii=False)
