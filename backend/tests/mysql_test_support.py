"""Synchronous inspection of an isolated native MySQL integration database."""
import asyncio
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlsplit, urlunsplit
import pymysql
from database import Database, connection_options


class Collection:
    def __init__(self, owner, collection):
        self.owner, self.collection = owner, collection

    def find(self, *args, **kwargs):
        return self.owner.run(self.collection.find(*args, **kwargs).to_list(None))

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.owner.run(getattr(self.collection, name)(*args, **kwargs))


class IsolatedDatabase:
    def __init__(self, uri, name):
        assert re.fullmatch(r'audit_mysql_[a-f0-9]{32}', name)
        self.name = name
        self.admin = pymysql.connect(**connection_options(uri))
        with self.admin.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        parsed = urlsplit(uri)
        self.uri = urlunsplit(parsed._replace(path='/' + name))
        self.loop = asyncio.new_event_loop()
        self.database = Database(self.uri)
        self.run(self.database.initialize())

    def run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def __getattr__(self, name):
        return Collection(self, self.database[name])

    def block_writes(self, table, enabled):
        assert table in {'assignment_letters', 'report_photos', 'audit_logs'}
        with self.admin.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER IF EXISTS `{self.name}`.`qa_guard_{table}`')
            if enabled:
                cursor.execute(f"CREATE TRIGGER `{self.name}`.`qa_guard_{table}` BEFORE INSERT ON `{self.name}`.`bm_{table}` FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='QA write guard'")

    def close(self):
        self.run(self.database.close())
        self.loop.close()
        with self.admin.cursor() as cursor:
            cursor.execute(f'DROP DATABASE `{self.name}`')
        self.admin.close()
