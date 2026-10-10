"""Native MySQL transactions shared by the operation and its audit writes."""
from functools import wraps
from database import connection_context
ENABLED = True
session_context = connection_context
async def run(client, operation):
    if not ENABLED: return await operation()  # Mock-only test fixtures.
    return await client.run_transaction(operation)
def decorator(client_getter):
    def wrap(function):
        @wraps(function)
        async def execute(*args, **kwargs):
            return await run(client_getter(), lambda: function(*args, **kwargs))
        return execute
    return wrap
