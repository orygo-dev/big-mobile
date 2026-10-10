"""Encrypted MySQL + local-file backup. Restore only to an isolated server."""
import argparse, base64, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC=b"BIGMOBILE1"


def crypt(source, target, key, decrypt=False):
    if len(key)!=32: raise ValueError("Backup key must decode to 32 bytes")
    with Path(source).open("rb") as incoming, Path(target).open("wb") as outgoing:
        if decrypt:
            if incoming.read(len(MAGIC))!=MAGIC: raise ValueError("Invalid encrypted backup")
            nonce=incoming.read(12)
            incoming.seek(-16,2); tag=incoming.read(16)
            stop=incoming.tell()-16
            incoming.seek(len(MAGIC)+12)
            cipher=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor()
        else:
            nonce=os.urandom(12); outgoing.write(MAGIC+nonce)
            cipher=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor()
            stop=None
        while True:
            size=min(1024*1024,stop-incoming.tell()) if decrypt else 1024*1024
            if size<=0: break
            chunk=incoming.read(size)
            if not chunk: break
            outgoing.write(cipher.update(chunk))
        outgoing.write(cipher.finalize())
        if not decrypt: outgoing.write(cipher.tag)


def safe_extract(archive, destination):
    root=Path(destination).resolve()
    with tarfile.open(archive) as package:
        for member in package.getmembers():
            target=(root/member.name).resolve()
            if not target.is_relative_to(root) or not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe backup member")
        package.extractall(root,filter="data")


import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mysql_connection import run_tool, identity, options


def backup(destination, uri, uploads, key, tool="mysqldump"):
    output=Path(destination).resolve(); output.parent.mkdir(parents=True,exist_ok=True); output.parent.chmod(0o700)
    if output.exists(): raise ValueError("Backup destination already exists")
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work=Path(temporary)
        run_tool(tool,uri,["--single-transaction","--quick","--hex-blob","--no-tablespaces","--set-gtid-purged=OFF"],work,work/"database.sql")
        if uploads:
            source=Path(uploads).resolve()
            if not source.is_dir(): raise ValueError("Local upload directory is missing")
            if any(item.is_symlink() for item in source.rglob('*')):
                raise ValueError("Upload backup must not follow symbolic links")
            shutil.copytree(source,work/"uploads",symlinks=False)
        else: raise ValueError("This backup mode requires local storage; configure S3 versioning/replication separately")
        with (work/"database.sql").open("rb") as archive:
            checksum=hashlib.file_digest(archive,"sha256").hexdigest()
        manifest={"created_at":datetime.now(timezone.utc).isoformat(),"storage":"local","mysql_sha256":checksum}
        (work/"manifest.json").write_text(json.dumps(manifest))
        bundle=work/"bundle.tar"
        with tarfile.open(bundle,"w") as package:
            for name in ("database.sql","uploads","manifest.json"): package.add(work/name,arcname=name)
        pending=work/"backup.pending"
        crypt(bundle,pending,key)
        pending.chmod(0o600)
        os.replace(pending,output)
    print("Encrypted backup completed:",output.name)


def restore(source, uri, uploads, key, tool="mysql", allow=False):
    if not allow: raise ValueError("Restore requires --isolated-target")
    if os.environ.get("MYSQL_URL") and identity(uri)==identity(os.environ["MYSQL_URL"]):
        raise ValueError("Refusing application database as restore target")
    import pymysql
    connection=options(uri)
    if connection.get('ssl_ca'):
        connection['ssl_verify_cert']=True;connection['ssl_verify_identity']=True
    probe=pymysql.connect(**connection)
    try:
        with probe.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s',(connection['database'],))
            if cursor.fetchone()[0]:raise ValueError('Restore target database must be empty')
    finally:probe.close()
    target=Path(uploads).resolve()
    if target.exists() and any(target.iterdir()): raise ValueError("Restore upload target must be empty")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        work=Path(temporary)
        crypt(source,work/"bundle.tar",key,decrypt=True)
        safe_extract(work/"bundle.tar",work/"data")
        data=work/"data"
        manifest=json.loads((data/"manifest.json").read_text())
        with (data/"database.sql").open("rb") as stream:
            if hashlib.file_digest(stream,"sha256").hexdigest()!=manifest["mysql_sha256"]: raise ValueError("Database archive checksum mismatch")
        run_tool(tool,uri,["--binary-mode=1"],work,data/"database.sql",restore=True)
        shutil.copytree(data/"uploads",target,dirs_exist_ok=True)
    print("Backup restored to isolated target; verify counts, files, and application login before switching traffic.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["backup","restore"]); parser.add_argument("archive")
    parser.add_argument("--uploads",required=True); parser.add_argument("--tool")
    parser.add_argument("--isolated-target",action="store_true")
    args=parser.parse_args()
    key=base64.b64decode(os.environ["BACKUP_ENCRYPTION_KEY"],validate=True)
    if args.mode=="backup": backup(args.archive,os.environ.get("BACKUP_MYSQL_URL") or os.environ["MYSQL_URL"],args.uploads,key,args.tool or "mysqldump")
    else: restore(args.archive,os.environ["RESTORE_MYSQL_URL"],args.uploads,key,args.tool or "mysql",args.isolated_target)
