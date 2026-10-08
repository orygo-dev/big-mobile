"""Encrypted MongoDB + local-file backup. Restore only to an isolated server."""
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


def run_tool(tool, uri, arguments, directory):
    # Credentials never appear in the process command line or printed logs.
    config=Path(directory)/"connection.yml"
    config.write_text("uri: "+json.dumps(uri)+"\n")
    config.chmod(0o600)
    try:
        result=subprocess.run([tool,"--config="+str(config),*arguments],capture_output=True,timeout=int(os.environ.get("BACKUP_TOOL_TIMEOUT_SECONDS","3600")))
        if result.returncode: raise RuntimeError(Path(tool).name+" failed; review server/tool permissions")
    finally: config.unlink(missing_ok=True)


def backup(destination, uri, uploads, key, tool="mongodump"):
    output=Path(destination).resolve(); output.parent.mkdir(parents=True,exist_ok=True); output.parent.chmod(0o700)
    if output.exists(): raise ValueError("Backup destination already exists")
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        work=Path(temporary)
        run_tool(tool,uri,["--oplog","--gzip","--archive="+str(work/"mongo.archive.gz")],work)
        if uploads:
            source=Path(uploads).resolve()
            if not source.is_dir(): raise ValueError("Local upload directory is missing")
            if any(item.is_symlink() for item in source.rglob('*')):
                raise ValueError("Upload backup must not follow symbolic links")
            shutil.copytree(source,work/"uploads",symlinks=False)
        else: raise ValueError("This backup mode requires local storage; configure S3 versioning/replication separately")
        with (work/"mongo.archive.gz").open("rb") as archive:
            checksum=hashlib.file_digest(archive,"sha256").hexdigest()
        manifest={"created_at":datetime.now(timezone.utc).isoformat(),"storage":"local","mongo_sha256":checksum}
        (work/"manifest.json").write_text(json.dumps(manifest))
        bundle=work/"bundle.tar"
        with tarfile.open(bundle,"w") as package:
            for name in ("mongo.archive.gz","uploads","manifest.json"): package.add(work/name,arcname=name)
        pending=work/"backup.pending"
        crypt(bundle,pending,key)
        pending.chmod(0o600)
        os.replace(pending,output)
    print("Encrypted backup completed:",output.name)


def restore(source, uri, uploads, key, tool="mongorestore", allow=False):
    if not allow: raise ValueError("Restore requires --isolated-target")
    if uri==os.environ.get("MONGO_URL"): raise ValueError("Refusing application database URI as restore target")
    from pymongo import MongoClient
    probe=MongoClient(uri,serverSelectionTimeoutMS=5000)
    if any(name not in {"admin","config","local"} for name in probe.list_database_names()):
        raise ValueError("Restore target must have no application databases")
    probe.close()
    target=Path(uploads).resolve()
    if target.exists() and any(target.iterdir()): raise ValueError("Restore upload target must be empty")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        work=Path(temporary)
        crypt(source,work/"bundle.tar",key,decrypt=True)
        safe_extract(work/"bundle.tar",work/"data")
        data=work/"data"
        manifest=json.loads((data/"manifest.json").read_text())
        with (data/"mongo.archive.gz").open("rb") as stream:
            if hashlib.file_digest(stream,"sha256").hexdigest()!=manifest["mongo_sha256"]: raise ValueError("Database archive checksum mismatch")
        run_tool(tool,uri,["--gzip","--oplogReplay","--archive="+str(data/"mongo.archive.gz")],work)
        shutil.copytree(data/"uploads",target,dirs_exist_ok=True)
    print("Backup restored to isolated target; verify counts, files, and application login before switching traffic.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["backup","restore"]); parser.add_argument("archive")
    parser.add_argument("--uploads",required=True); parser.add_argument("--tool")
    parser.add_argument("--isolated-target",action="store_true")
    args=parser.parse_args()
    key=base64.b64decode(os.environ["BACKUP_ENCRYPTION_KEY"],validate=True)
    if args.mode=="backup": backup(args.archive,os.environ.get("BACKUP_MONGO_URL") or os.environ["MONGO_URL"],args.uploads,key,args.tool or "mongodump")
    else: restore(args.archive,os.environ["RESTORE_MONGO_URL"],args.uploads,key,args.tool or "mongorestore",args.isolated_target)
