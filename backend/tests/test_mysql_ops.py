"""Native SQL backup/restore and atomic legacy import on disposable databases."""
import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
import pytest
from mysql_test_support import IsolatedDatabase

pytestmark=pytest.mark.skipif(not os.environ.get('MYSQL_TEST_URL'),reason='Requires an isolated native MySQL test account')


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_native_encrypted_backup_restore_and_target_protection(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    source=IsolatedDatabase(os.environ['MYSQL_TEST_URL'],'audit_mysql_'+uuid.uuid4().hex)
    target=IsolatedDatabase(os.environ['MYSQL_TEST_URL'],'audit_mysql_'+uuid.uuid4().hex)
    ops=module('mysql_backup',root/'deploy/backup.py')
    source.users.insert_one({'id':'backup-admin','name':'Preserved user','company_id':'backup-company'})
    source.companies.insert_one({'id':'backup-company','nama':'Preserved company'})
    # Restore accepts a fresh database, not initialized application tables.
    for table in target.run(target.database.list_collection_names()):
        target.run(target.database.execute(f'DROP TABLE `bm_{table}`'))
    uploads=tmp_path/'uploads';uploads.mkdir();(uploads/'proof.txt').write_text('Private proof')
    restored=tmp_path/'restored';archive=tmp_path/'backup.enc';key=os.urandom(32)
    clients=Path(os.environ.get('MYSQL_CLIENT_DIR',''))
    dump=str(clients/'mysqldump.exe') if os.name=='nt' else 'mysqldump'
    mysql=str(clients/'mysql.exe') if os.name=='nt' else 'mysql'
    monkeypatch.setenv('MYSQL_URL',source.uri)
    try:
        ops.backup(archive,source.uri,uploads,key,dump)
        with pytest.raises(ValueError,match='application database'):
            ops.restore(archive,source.uri,restored,key,mysql,allow=True)
        ops.restore(archive,target.uri,restored,key,mysql,allow=True)
        assert target.users.find_one({'id':'backup-admin'})['name']=='Preserved user'
        assert target.companies.count_documents({})==1
        assert (restored/'proof.txt').read_bytes()==(uploads/'proof.txt').read_bytes()
        with pytest.raises(ValueError,match='empty'):
            ops.restore(archive,target.uri,tmp_path/'another',key,mysql,allow=True)
    finally:source.close();target.close()


def test_legacy_import_preserves_records_and_rejects_nonempty_target(tmp_path,monkeypatch):
    from migrate_legacy import migrate
    database=IsolatedDatabase(os.environ['MYSQL_TEST_URL'],'audit_mysql_'+uuid.uuid4().hex)
    document={'id':'legacy-user','company_id':'legacy-company','password_hash':'preserved-hash','metadata':{'version':2}}
    path=tmp_path/'users.jsonl';path.write_text(json.dumps(document)+'\n')
    manifest={'format':1,'collections':{'users':{'count':1,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setenv('MYSQL_URL',database.uri)
    try:
        asyncio.run(migrate(tmp_path))
        assert database.users.find_one({'id':'legacy-user'})==document
        with pytest.raises(ValueError,match='empty'):asyncio.run(migrate(tmp_path))
        assert database.users.count_documents({})==1
        path.write_text('{}\n')
        with pytest.raises(ValueError,match='checksum'):asyncio.run(migrate(tmp_path))
        assert database.users.count_documents({})==1
        assert database.users.find_one({'id':"legacy-user' OR 1=1 --"}) is None
        database.users.update_one({'id':'legacy-user'},{'$set':{'attachments':[{'storage_path':'private/proof.jpg'}]}})
        assert database.users.find_one({'attachments.storage_path':'private/proof.jpg'})['id']=='legacy-user'
        # Production preflight verifies native tenant joins, rollback and private file storage.
        import bcrypt
        from manage import preflight
        import storage
        monkeypatch.setattr(storage,'STORAGE_BACKEND','local')
        monkeypatch.setattr(storage,'LOCAL_STORAGE_DIR',tmp_path/'private-uploads')
        database.users.update_one({'id':'legacy-user'},{'$set':{'role':'admin','status':'aktif','password_hash':bcrypt.hashpw(os.urandom(32).hex().encode(),bcrypt.gensalt()).decode()}})
        database.companies.insert_one({'id':'legacy-company','nama':'Migrated company'})
        assert database.run(preflight(database.database,database.database))==0
    finally:database.close()
