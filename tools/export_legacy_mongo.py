"""One-time export. Install tools/requirements-migration.txt separately."""
import argparse
import hashlib
import json
import os
from datetime import datetime, date
from pathlib import Path
from pymongo import MongoClient


def encode(value):
    if isinstance(value, (datetime, date)): return value.isoformat()
    raise TypeError('Unsupported legacy value; inspect source before migration')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    args.destination.mkdir(mode=0o700,parents=True,exist_ok=False)
    client=MongoClient(os.environ['SOURCE_MONGO_URL'],serverSelectionTimeoutMS=10000)
    source=client[os.environ['SOURCE_MONGO_DATABASE']]
    manifest={'format':1,'collections':{}}
    try:
        for name in source.list_collection_names():
            if not name.replace('_','').isalnum():raise ValueError('Invalid collection name')
            count=0
            path=args.destination/(name+'.jsonl')
            with path.open('w',encoding='utf-8') as stream:
                for document in source[name].find({}):
                    if 'id' in document:document.pop('_id',None)
                    elif '_id' in document and not isinstance(document['_id'],str):document.pop('_id')
                    stream.write(json.dumps(document,default=encode,ensure_ascii=False)+'\n');count+=1
            path.chmod(0o600)
            manifest['collections'][name]={'count':count,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        (args.destination/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print('Export completed; source data was retained.')
    finally:client.close()


if __name__=='__main__':main()
