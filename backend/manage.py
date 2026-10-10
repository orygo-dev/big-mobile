"""MySQL production administration; passwords never appear in CLI arguments."""
import argparse, asyncio, getpass, json, os, secrets, uuid
from pathlib import Path
import bcrypt
from dotenv import load_dotenv

async def preflight(database, client):
    problems=[]
    for table,key in [('users','email'),('accounts','id'),('assignments','active_key'),('field_reports','submission_key')]:
        rows=await database.execute(f'SELECT g_{key},COUNT(*) FROM bm_{table} WHERE g_{key} IS NOT NULL GROUP BY g_{key} HAVING COUNT(*)>1 LIMIT 1',fetch=True)
        if rows:problems.append(f'Duplicate {table}.{key}')
    references=[('accounts','client_id','clients'),('accounts','surat_kuasa_id','power_of_attorneys'),('assignments','account_id','accounts'),('assignments','officer_id','users'),('field_reports','assignment_id','assignments'),('chat_messages','assignment_id','assignments'),('chat_messages','sender_id','users'),('chat_reads','assignment_id','assignments'),('chat_reads','user_id','users')]
    for table,field,parent in references:
        rows=await database.execute(f'SELECT 1 FROM bm_{table} c LEFT JOIN bm_{parent} p ON c.g_{field}=p.g_id AND c.g_company_id=p.g_company_id WHERE p._pk IS NULL LIMIT 1',fetch=True)
        if rows:problems.append(f'Invalid tenant/reference in {table}.{field}')
    if await database.execute('SELECT 1 FROM bm_users u LEFT JOIN bm_companies c ON u.g_company_id=c.g_id WHERE c._pk IS NULL LIMIT 1',fetch=True):problems.append('A user references a missing company')
    active=await database.users.count_documents({'role':'admin','status':'aktif'})
    if not active:problems.append('Create an active production administrator')
    for user in await database.users.find({}, {'password_hash':1}).to_list(None):
        try:
            if any(bcrypt.checkpw(p.encode(),user.get('password_hash','').encode()) for p in ('admin123','petugas123','password','12345678')):problems.append('A default/demo password is still enabled');break
        except ValueError:problems.append('Invalid password hash');break
    if problems:print(json.dumps({'ready':False,'problems':problems},indent=2));return 1
    class ProbeRollback(Exception):pass
    identity=uuid.uuid4().hex
    async def probe():
        await database.production_checks.insert_one({'id':identity});raise ProbeRollback()
    try:await database.run_transaction(probe)
    except ProbeRollback:pass
    if await database.production_checks.find_one({'id':identity}):raise RuntimeError('Transaction rollback probe failed')
    import storage
    await asyncio.to_thread(storage.init_storage)
    administrator=await database.users.find_one({'role':'admin','status':'aktif'})
    path=f"fieldcollector/companies/{administrator['company_id']}/checks/{uuid.uuid4().hex}.txt"
    try:
        await asyncio.to_thread(storage.put_object,path,b'BIG Mobile readiness probe','text/plain')
        if (await asyncio.to_thread(storage.get_object,path))[0]!=b'BIG Mobile readiness probe':raise RuntimeError('Storage verification failed')
    finally:await asyncio.to_thread(storage.delete_object,path)
    print(json.dumps({'ready':True,'database':'mysql','transactions':'verified','storage':'verified','active_administrators':active}));return 0

async def bootstrap(database,name,email,company_name):
    if await database.users.count_documents({}) or await database.companies.count_documents({}):raise ValueError('Bootstrap only accepts an empty application database')
    password=getpass.getpass('New admin password (12-72 bytes): ')
    if len(password)<12 or len(password.encode())>72 or password!=getpass.getpass('Confirm password: '):raise ValueError('Invalid password/confirmation')
    company=str(uuid.uuid4())
    async def commit():
        await database.companies.insert_one({'id':company,'nama':company_name,'company_code':secrets.token_hex(4).upper(),'app_name':'BIG Mobile'})
        await database.users.insert_one({'id':str(uuid.uuid4()),'company_id':company,'name':name,'email':email.strip().lower(),'role':'admin','status':'aktif','token_version':0,'password_hash':bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()})
    await database.run_transaction(commit)
    print('Production administrator created; password was not logged.')

async def main(args):
    import server
    try:
        await server.initialize_database()
        if args.command=='init-db':print('MySQL schema and indexes ready.');return 0
        if args.command=='preflight':return await preflight(server.db,server.db)
        if not all((args.name,args.email,args.company)):raise ValueError('Bootstrap requires --name, --email, --company')
        await bootstrap(server.db,args.name,args.email,args.company);return 0
    finally:await server.db.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['init-db','preflight','bootstrap-admin']);parser.add_argument('--env',type=Path)
    parser.add_argument('--name');parser.add_argument('--email');parser.add_argument('--company');args=parser.parse_args()
    if args.env:load_dotenv(args.env,override=True)
    try:raise SystemExit(asyncio.run(main(args)))
    except Exception as error:print('Administration failed:',type(error).__name__);raise SystemExit(1)
