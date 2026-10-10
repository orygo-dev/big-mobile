"""Native MySQL/InnoDB repositories; entity tables with indexed JSON metadata."""
import asyncio, copy, hashlib, json, os, re, ssl
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, date, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit, unquote, parse_qs
import aiomysql
import pymysql

class DuplicateKeyError(Exception): pass
class ConnectionFailure(Exception): pass
class ReturnDocument:
    BEFORE=False
    AFTER=True

connection_context=ContextVar('mysql_connection',default=None)
TABLES=('users','companies','clients','power_of_attorneys','accounts','assignments','assignment_letters','field_reports','report_photos','documents','document_templates','audit_logs','debtors','counters','rate_limits','revoked_tokens','login_attempts','upload_intents','idempotency','chat_messages','chat_reads','production_checks')
TEXT_FIELDS=('id','company_id','email','active_key','submission_key','officer_id','petugas_id','assignment_id','account_id','client_id','surat_kuasa_id','power_of_attorney_id','report_id','sender_id','user_id','client_message_id','storage_path','status','created_at','chat_updated_at','expires_at','identifier','masa_berlaku')
NUMBER_FIELDS=('sequence','chat_sequence','seq','count','token_version','relation_version','report_version')

def connection_options(uri=None):
    parsed=urlsplit(uri or os.environ.get('MYSQL_URL',''))
    name=unquote(parsed.path.lstrip('/'))
    if parsed.scheme!='mysql' or not parsed.hostname or not parsed.username or not re.fullmatch(r'[A-Za-z0-9_]{1,64}',name):
        raise ValueError('MYSQL_URL must contain a MySQL user, host and database')
    result={'host':parsed.hostname,'port':parsed.port or 3306,'user':unquote(parsed.username),'password':unquote(parsed.password or ''),'db':name,'charset':'utf8mb4','connect_timeout':10,'autocommit':True}
    ca=parse_qs(parsed.query).get('ssl_ca',[None])[0]
    if ca:result['ssl']=ssl.create_default_context(cafile=ca)
    return result

def serialize(value):
    def encode(item):
        if isinstance(item,(date,datetime)):return item.isoformat()
        raise TypeError(type(item).__name__)
    return json.dumps(value,default=encode,ensure_ascii=False,allow_nan=False,separators=(',',':'))

def json_path(field):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*',field):raise ValueError('Invalid repository field')
    parts=field.split('.')
    if parts[0]=='attachments' and len(parts)>1:parts[0]+='[*]'
    return '$.'+'.'.join(parts)

def expression(field,alias=''):
    prefix=alias+'.' if alias else ''
    if field in TEXT_FIELDS or field in NUMBER_FIELDS:return f'{prefix}`g_{field}`'
    return f"NULLIF(JSON_UNQUOTE(JSON_EXTRACT({prefix}payload, '{json_path(field)}')), 'null')"

def compile_query(query,alias=''):
    clauses=[];params=[];prefix=alias+'.' if alias else ''
    def equal(field,value):
        path=json_path(field)
        if value is None:return f"(JSON_EXTRACT({prefix}payload,'{path}') IS NULL OR JSON_TYPE(JSON_EXTRACT({prefix}payload,'{path}'))='NULL')",[]
        if field in TEXT_FIELDS or field in NUMBER_FIELDS:return f'COALESCE({expression(field,alias)}=%s,0)',[value]
        return f"COALESCE(JSON_CONTAINS(JSON_EXTRACT({prefix}payload,'{path}'),CAST(%s AS JSON)),0)",[serialize(value)]
    for field,value in (query or {}).items():
        if field in {'$and','$or'}:
            nested=[compile_query(item,alias) for item in value]
            clauses.append('('+(' AND ' if field=='$and' else ' OR ').join(item[0] for item in nested)+')' if nested else ('1' if field=='$and' else '0'))
            params.extend(p for item in nested for p in item[1]);continue
        target=expression(field,alias)
        if not isinstance(value,dict):
            clause,values=equal(field,value);clauses.append(clause);params.extend(values);continue
        for op,operand in value.items():
            if op=='$options':continue
            if op in {'$in','$nin'}:
                nested=[equal(field,item) for item in operand];clause='('+' OR '.join(item[0] for item in nested)+')' if nested else '0'
                clauses.append(f'NOT ({clause})' if op=='$nin' else clause);params.extend(p for item in nested for p in item[1])
            elif op=='$ne':
                clause,values=equal(field,operand);clauses.append(f'NOT ({clause})');params.extend(values)
            elif op in {'$gt','$gte','$lt','$lte'}:
                sign={'$gt':'>','$gte':'>=','$lt':'<','$lte':'<='}[op]
                clauses.append(f'COALESCE({target}{sign}%s,0)');params.append(operand.isoformat() if isinstance(operand,(date,datetime)) else operand)
            elif op=='$exists':clauses.append(f"JSON_CONTAINS_PATH({prefix}payload,'one','{json_path(field)}')=%s");params.append(int(operand))
            elif op=='$type':
                if operand!='string':raise ValueError('Unsupported type filter')
                clauses.append(f"JSON_TYPE(JSON_EXTRACT({prefix}payload,'{json_path(field)}'))='STRING'")
            elif op=='$regex':clauses.append(f'COALESCE(REGEXP_LIKE({target},%s,%s),0)');params.extend([operand,'i' if 'i' in value.get('$options','') else 'c'])
            else:raise ValueError('Unsupported repository operation: '+op)
    return ' AND '.join(clauses) or '1',params

def project(doc,projection):
    if not projection:return doc
    included=[k for k,v in projection.items() if v and k!='_id']
    if included:return {k:doc[k] for k in included if k in doc}
    return {k:v for k,v in doc.items() if projection.get(k,1)}

def get_path(doc,field,default=None):
    for key in field.split('.'):
        if not isinstance(doc,dict) or key not in doc:return default
        doc=doc[key]
    return doc

def set_path(doc,field,value,remove=False):
    keys=field.split('.')
    for key in keys[:-1]:doc=doc.setdefault(key,{})
    if remove:doc.pop(keys[-1],None)
    else:doc[keys[-1]]=copy.deepcopy(value)

def updated(doc,changes,inserting=False):
    result=copy.deepcopy(doc)
    for op,values in changes.items():
        if op=='$setOnInsert' and not inserting:continue
        for field,value in values.items():
            if op in {'$set','$setOnInsert'}:set_path(result,field,value)
            elif op=='$unset':set_path(result,field,None,True)
            elif op=='$inc':set_path(result,field,get_path(result,field,0)+value)
            elif op=='$max':set_path(result,field,max(get_path(result,field,value),value))
            else:raise ValueError('Unsupported update: '+op)
    return result

def record_key(doc):
    identity=doc.get('id',doc.get('_id'))
    if identity is None:return hashlib.sha256(serialize(doc).encode()).hexdigest()
    if not isinstance(identity,str) or len(identity)>191:raise ValueError('Invalid entity key')
    return identity

class Cursor:
    def __init__(self,collection,query,projection=None):self.collection,self.query,self.projection=collection,query,projection;self.order=[];self.offset=0;self.maximum=None
    def sort(self,field,direction=1):self.order=field if isinstance(field,list) else [(field,direction)];return self
    def skip(self,count):self.offset=count;return self
    def limit(self,count):self.maximum=count;return self
    async def to_list(self,length=None):
        where,params=compile_query(self.query);sql=f'SELECT _pk,payload FROM `{self.collection.table}` WHERE {where}'
        if self.order:sql+=' ORDER BY '+', '.join(expression(field)+(' DESC' if direction<0 else ' ASC') for field,direction in self.order)
        maximum=min(length,self.maximum) if length is not None and self.maximum is not None else length if length is not None else self.maximum
        if maximum is not None:sql+=' LIMIT %s OFFSET %s';params.extend([maximum,self.offset])
        elif self.offset:sql+=' LIMIT 18446744073709551615 OFFSET %s';params.append(self.offset)
        if connection_context.get() is not None:sql+=' FOR UPDATE'
        rows=await self.collection.database.execute(sql,params,fetch=True)
        return [project(json.loads(row[1]),self.projection) for row in rows]

class Collection:
    def __init__(self,database,name):self.database,self.name,self.table=database,name,'bm_'+name
    def find(self,query=None,projection=None):return Cursor(self,query or {},projection)
    async def find_one(self,query,projection=None):
        rows=await self.find(query,projection).to_list(1);return rows[0] if rows else None
    async def count_documents(self,query):
        where,params=compile_query(query);rows=await self.database.execute(f'SELECT COUNT(*) FROM `{self.table}` WHERE {where}',params,fetch=True);return int(rows[0][0])
    async def distinct(self,field,query):
        where,params=compile_query(query);rows=await self.database.execute(f"SELECT DISTINCT JSON_EXTRACT(payload,'{json_path(field)}') FROM `{self.table}` WHERE {where}",params,fetch=True);values=[]
        for row in rows:
            if row[0] is not None:
                value=json.loads(row[0]);values.extend(value if isinstance(value,list) else [value])
        return list(dict.fromkeys(values))
    async def insert_one(self,doc):
        identity=record_key(doc);await self.database.execute(f'INSERT INTO `{self.table}` (_pk,payload) VALUES (%s,%s)',[identity,serialize(doc)]);return SimpleNamespace(inserted_id=identity)
    async def insert_many(self,documents):
        async def operation():return [await self.insert_one(item) for item in documents]
        return await self.database.run_transaction(operation)
    async def _change(self,query,changes,upsert=False,many=False,return_document=None):
        async def operation():
            where,params=compile_query(query);sql=f'SELECT _pk,payload FROM `{self.table}` WHERE {where}'+('' if many else ' LIMIT 1')+' FOR UPDATE'
            rows=await self.database.execute(sql,params,fetch=True)
            if not rows and upsert:
                base={k:v for k,v in query.items() if not k.startswith('$') and not isinstance(v,dict)};result=updated(base,changes,True);await self.insert_one(result)
                return result if return_document is True else None if return_document is False else SimpleNamespace(matched_count=0,modified_count=0,upserted_id=record_key(result))
            result=None;modified=0
            for identity,payload in rows:
                original=json.loads(payload);result=updated(original,changes)
                if result!=original:await self.database.execute(f'UPDATE `{self.table}` SET payload=%s WHERE _pk=%s',[serialize(result),identity]);modified+=1
                if return_document is False:result=original
            return result if return_document is not None else SimpleNamespace(matched_count=len(rows),modified_count=modified,upserted_id=None)
        return await self.database.run_transaction(operation)
    async def update_one(self,query,changes,upsert=False):return await self._change(query,changes,upsert)
    async def update_many(self,query,changes):return await self._change(query,changes,many=True)
    async def find_one_and_update(self,query,changes,upsert=False,return_document=False):return await self._change(query,changes,upsert,return_document=bool(return_document))
    async def delete_one(self,query):
        where,params=compile_query(query);count=await self.database.execute(f'DELETE FROM `{self.table}` WHERE {where} LIMIT 1',params);return SimpleNamespace(deleted_count=count)
    async def delete_many(self,query):
        where,params=compile_query(query);count=await self.database.execute(f'DELETE FROM `{self.table}` WHERE {where}',params);return SimpleNamespace(deleted_count=count)
    async def create_index(self,keys,unique=False,**options):
        if 'expireAfterSeconds' in options:return 'application_expiry_worker'
        if isinstance(keys,str):keys=[(keys,1)]
        if any(field not in TEXT_FIELDS and field not in NUMBER_FIELDS for field,_ in keys):raise ValueError('Unmapped index field')
        name='ix_'+hashlib.sha256((self.name+serialize(keys)+str(unique)).encode()).hexdigest()[:20]
        rows=await self.database.execute('SELECT 1 FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name=%s AND index_name=%s',[self.table,name],fetch=True)
        if not rows:
            fields=', '.join(f'`g_{key}`' for key,_ in keys)
            await self.database.execute(f"ALTER TABLE `{self.table}` ADD {'UNIQUE ' if unique else ''}INDEX `{name}` ({fields})")
        return name

class Database:
    def __init__(self,uri=None):self.options=connection_options(uri);self.name=self.options['db'];self.pool=None;self.client=self;self._pool_lock=asyncio.Lock()
    def __getitem__(self,name):
        if name not in TABLES:raise ValueError('Unknown application table')
        return Collection(self,name)
    def __getattr__(self,name):
        if name in TABLES:return self[name]
        raise AttributeError(name)
    async def connect(self):
        if self.pool is None:
            async with self._pool_lock:
                if self.pool is None:self.pool=await aiomysql.create_pool(**self.options,minsize=1,maxsize=int(os.environ.get('MYSQL_POOL_SIZE','10')),pool_recycle=300,init_command="SET time_zone='+00:00'")
        return self.pool
    @asynccontextmanager
    async def connection(self):
        current=connection_context.get()
        if current is not None:yield current;return
        pool=await self.connect()
        async with pool.acquire() as connection:yield connection
    async def execute(self,sql,parameters=None,fetch=False):
        try:
            async with self.connection() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(sql,parameters);return await cursor.fetchall() if fetch else cursor.rowcount
        except pymysql.IntegrityError as error:
            if error.args[0]==1062:raise DuplicateKeyError('Duplicate entity key') from error
            raise
        except pymysql.OperationalError as error:
            if error.args[0] in {2002,2003,2006,2013}:raise ConnectionFailure('MySQL connection unavailable') from error
            raise
    async def run_transaction(self,operation):
        if connection_context.get() is not None:return await operation()
        for attempt in range(4):
            try:
                async with self.connection() as connection:
                    await connection.begin();token=connection_context.set(connection)
                    try:result=await operation();await connection.commit();return result
                    except BaseException:await connection.rollback();raise
                    finally:connection_context.reset(token)
            except (pymysql.OperationalError,DuplicateKeyError) as error:
                if (not isinstance(error,DuplicateKeyError) and error.args[0] not in {1205,1213}) or attempt==3:raise
                await asyncio.sleep(.03*(attempt+1))
    async def initialize(self):
        await self.command('ping')
        version=(await self.execute('SELECT VERSION()',fetch=True))[0][0]
        if 'mariadb' in version.lower() or tuple(int(n) for n in version.split('-')[0].split('.')[:3])<(8,0,21):
            raise RuntimeError('MySQL 8.0.21 or newer is required; use MySQL 8.4 LTS')
        async with self.connection() as connection:
            token=connection_context.set(connection)
            try:
                lock_name='big_mobile_schema_'+hashlib.sha256(self.name.encode()).hexdigest()[:32]
                locked=await self.execute('SELECT GET_LOCK(%s,30)',[lock_name],fetch=True)
                if locked[0][0]!=1:raise RuntimeError('Schema initialization is busy')
                try:
                    for name in TABLES:
                        columns=['_pk VARCHAR(191) COLLATE utf8mb4_bin PRIMARY KEY','payload JSON NOT NULL']
                        for field in TEXT_FIELDS:
                            if field=='masa_berlaku' and name!='assignment_letters':continue
                            size=191 if field not in {'storage_path','email','identifier'} else 512
                            columns.append(f"`g_{field}` VARCHAR({size}) COLLATE utf8mb4_bin GENERATED ALWAYS AS (NULLIF(JSON_UNQUOTE(JSON_EXTRACT(payload,'$.{field}')),'null')) STORED")
                        for field in NUMBER_FIELDS:columns.append(f"`g_{field}` DECIMAL(30,6) GENERATED ALWAYS AS (CAST(JSON_UNQUOTE(JSON_EXTRACT(payload,'$.{field}')) AS DECIMAL(30,6))) STORED")
                        await self.execute(f"CREATE TABLE IF NOT EXISTS `bm_{name}` ({', '.join(columns)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin")
                        existing={row[0] for row in await self.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s',['bm_'+name],fetch=True)}
                        for column in columns[2:]:
                            if column.split('`')[1] not in existing:
                                await self.execute(f'ALTER TABLE `bm_{name}` ADD COLUMN {column}')
                        engine=(await self.execute('SELECT engine FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s',['bm_'+name],fetch=True))[0][0]
                        if engine!='InnoDB':raise RuntimeError('Application tables must use InnoDB')
                finally:await self.execute('SELECT RELEASE_LOCK(%s)',[lock_name])
            finally:connection_context.reset(token)
    async def command(self,name):
        if name!='ping':raise ValueError('Unsupported database command')
        await self.execute('SELECT 1',fetch=True);return {'ok':1}
    async def list_collection_names(self):
        rows=await self.execute('SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE()',fetch=True);return [row[0][3:] for row in rows if row[0].startswith('bm_') and row[0][3:] in TABLES]
    async def purge_expired(self):
        for name in ('idempotency','revoked_tokens','login_attempts','rate_limits'):await self[name].delete_many({'expires_at':{'$lt':datetime.now(timezone.utc).isoformat()}})
    async def unread_messages(self,user):
        query={'company_id':user['company_id'],'sender_id':{'$ne':user['id']}}
        if user['role']=='petugas':query['officer_id']=user['id']
        where,params=compile_query(query,'m')
        sql=f'SELECT COUNT(*) FROM bm_chat_messages m LEFT JOIN bm_chat_reads r ON r.g_company_id=m.g_company_id AND r.g_assignment_id=m.g_assignment_id AND r.g_user_id=%s WHERE {where} AND m.g_sequence>COALESCE(r.g_sequence,0)'
        rows=await self.execute(sql,[user['id'],*params],fetch=True);return int(rows[0][0])
    async def close(self):
        if self.pool:self.pool.close();await self.pool.wait_closed();self.pool=None;await asyncio.sleep(0)
