"""Import verified legacy export into an EMPTY MySQL application database."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv
from database import Database, TABLES


async def migrate(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('format')!=1:raise ValueError('Unsupported export format')
    if set(manifest['collections'])-set(TABLES):raise ValueError('Unknown legacy collections; map them before importing')
    for name,info in manifest['collections'].items():
        path=directory/(name+'.jsonl')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Export checksum mismatch')
        with path.open(encoding='utf-8') as stream:
            if sum(1 for _ in stream)!=info['count']:raise ValueError('Export count mismatch')
    database=Database()
    try:
        await database.initialize()
        async def import_all():
            for name in TABLES:
                if await database[name].count_documents({}):raise ValueError('Target database must be empty')
            for name,info in manifest['collections'].items():
                with (directory/(name+'.jsonl')).open(encoding='utf-8') as stream:
                    for line in stream:await database[name].insert_one(json.loads(line))
                if await database[name].count_documents({})!=info['count']:raise RuntimeError('Imported count mismatch')
        await database.run_transaction(import_all)
        print('Migration committed; all collection counts matched. Source export was retained.')
    finally:await database.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--env',type=Path);args=parser.parse_args()
    if args.env:load_dotenv(args.env,override=True)
    asyncio.run(migrate(args.directory.resolve()))
