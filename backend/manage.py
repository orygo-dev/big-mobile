"""Production administration without exposing passwords in arguments or logs."""
import argparse
import getpass
import json
import os
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient


def preflight(database, client):
    problems = []
    hello = client.admin.command('hello')
    if not hello.get('setName') and hello.get('msg') != 'isdbgrid':
        problems.append('MongoDB must support transactions')
    uri = urlsplit(os.environ['MONGO_URL'])
    options = parse_qs(uri.query.lower())
    if not uri.username or not uri.password:
        problems.append('MongoDB authentication is required')
    tls=options.get('tls',options.get('ssl'))
    if (uri.scheme=='mongodb+srv' and tls==['false']) or (uri.scheme!='mongodb+srv' and tls!=['true']):
        problems.append('MongoDB TLS is required')
    if any(options.get(name) == ['true'] for name in ('tlsallowinvalidcertificates', 'tlsallowinvalidhostnames', 'tlsinsecure')):
        problems.append('MongoDB certificate verification must remain enabled')
    for collection, key in [('users','email'),('accounts','id'),('assignments','active_key'),('field_reports','submission_key')]:
        duplicates = database[collection].aggregate([
            {'$match':{key:{'$type':'string','$ne':''}}},
            {'$group':{'_id':'$'+key,'count':{'$sum':1}}},
            {'$match':{'count':{'$gt':1}}}, {'$limit':1}])
        if next(duplicates, None): problems.append(f'Duplicate {collection}.{key}')
    references = [('accounts','client_id','clients'), ('accounts','surat_kuasa_id','power_of_attorneys'), ('assignments','account_id','accounts'), ('assignments','officer_id','users'), ('field_reports','assignment_id','assignments')]
    for collection, field, parent in references:
        for item in database[collection].find({}, {field:1,'company_id':1}):
            reference = item.get(field)
            if not reference or not database[parent].find_one({'id':reference,'company_id':item.get('company_id')}, {'_id':1}):
                problems.append(f'Invalid tenant/reference in {collection}.{field}')
                break
    for user in database.users.find({}, {'company_id':1}):
        if not database.companies.find_one({'id':user.get('company_id')},{'_id':1}):
            problems.append('A user references a missing company'); break
    active_admins = database.users.count_documents({'role':'admin','status':'aktif'})
    if not active_admins: problems.append('Create an active production administrator')
    for user in database.users.find({}, {'password_hash':1}):
        encoded = user.get('password_hash','').encode()
        try:
            if any(bcrypt.checkpw(password.encode(), encoded) for password in ('admin123','petugas123','password','12345678')):
                problems.append('A default/demo password is still enabled'); break
        except ValueError:
            problems.append('An invalid password hash exists'); break
    monitor = os.environ.get('MONITOR_TOKEN','')
    if len(monitor) < 32 or 'replace-with' in monitor:
        problems.append('Configure a separate random MONITOR_TOKEN')
    if problems:
        print(json.dumps({'ready':False,'problems':problems}, indent=2)); return 1
    # A write/abort probe verifies real transaction permissions without committing data.
    with client.start_session() as session:
        session.start_transaction()
        try: database.production_checks.insert_one({'id':uuid.uuid4().hex}, session=session)
        finally: session.abort_transaction()
    import storage
    storage.init_storage()
    administrator=database.users.find_one({'role':'admin','status':'aktif'},{'company_id':1})
    path=f"fieldcollector/companies/{administrator['company_id']}/checks/{uuid.uuid4().hex}.txt"
    try:
        storage.put_object(path,b'BIG Mobile readiness probe','text/plain')
        if storage.get_object(path)[0] != b'BIG Mobile readiness probe':
            raise RuntimeError('Storage verification failed')
    finally: storage.delete_object(path)
    print(json.dumps({'ready':True,'transactions':'verified','storage':'write/read/delete verified','active_administrators':active_admins})); return 0


def bootstrap(database, name, email, company_name):
    if database.users.count_documents({}) or database.companies.count_documents({}):
        raise ValueError('Bootstrap only accepts an empty application database; use existing account settings for password changes')
    password = getpass.getpass('New admin password (12–72 bytes): ')
    if len(password) < 12 or len(password.encode()) > 72 or password != getpass.getpass('Confirm password: '):
        raise ValueError('Password must match and satisfy the length policy')
    company = str(uuid.uuid4())
    with database.client.start_session() as session:
        with session.start_transaction():
            database.companies.insert_one({'id':company,'nama':company_name,'company_code':secrets.token_hex(4).upper(),'app_name':'BIG Mobile'},session=session)
            database.users.insert_one({'id':str(uuid.uuid4()),'company_id':company,'name':name,'email':email.strip().lower(),'role':'admin','status':'aktif','token_version':0,'password_hash':bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()},session=session)
    print('Production administrator created; password was not logged.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command', choices=['preflight','bootstrap-admin'])
    parser.add_argument('--env',type=Path)
    parser.add_argument('--name'); parser.add_argument('--email'); parser.add_argument('--company')
    args=parser.parse_args()
    if args.env: load_dotenv(args.env,override=True)
    import security
    security.validate_configuration()
    try:
        with MongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=10000) as client:
            database=client[os.environ['DB_NAME']]
            if args.command=='preflight': raise SystemExit(preflight(database,client))
            if not all((args.name,args.email,args.company)): parser.error('Bootstrap requires --name, --email, --company')
            bootstrap(database,args.name,args.email,args.company)
    except Exception as error:
        print('Administration failed:',type(error).__name__)
        raise SystemExit(1)
