"""Propagate one Mongo session through a business operation and its audit writes."""
from contextvars import ContextVar
from functools import wraps
import os
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

session_context = ContextVar("mongo_transaction_session", default=None)
ENABLED = os.environ.get("DB_TRANSACTIONS", "true" if os.environ.get("APP_ENV") == "production" else "false").lower() == "true"


class Collection:
    def __init__(self, collection):
        self.collection = collection

    def __getattr__(self, name):
        target = getattr(self.collection, name)
        if not callable(target):
            return target
        def call(*args, **kwargs):
            session = session_context.get()
            if session is not None:
                kwargs.setdefault("session", session)
            return target(*args, **kwargs)
        return call


class Database:
    def __init__(self, database):
        self.database = database

    def __getattr__(self, name):
        if name in {"command", "client", "name", "list_collection_names"}:
            return getattr(self.database, name)
        return Collection(self.database[name])


async def run(client, operation):
    if not ENABLED or session_context.get() is not None:
        return await operation()
    async with await client.start_session() as session:
        async def callback(active_session):
            token = session_context.set(active_session)
            try:
                return await operation()
            finally:
                session_context.reset(token)
        # Only DB operations belong in callbacks: the driver can replay them.
        return await session.with_transaction(callback, read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority", wtimeout=10000), max_commit_time_ms=10000)


def decorator(client_getter):
    def wrap(function):
        @wraps(function)
        async def execute(*args, **kwargs):
            return await run(client_getter(), lambda: function(*args, **kwargs))
        return execute
    return wrap
