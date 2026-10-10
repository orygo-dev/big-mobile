"""Native client config; credentials are never command-line arguments."""
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs


def options(uri):
    value = urlsplit(uri)
    import re
    database = unquote(value.path.lstrip('/'))
    if value.scheme != 'mysql' or not value.username or not value.hostname or not re.fullmatch(r'[A-Za-z0-9_]{1,64}', database):
        raise ValueError('Invalid MySQL connection URL')
    result = dict(host=value.hostname, port=value.port or 3306, user=unquote(value.username), password=unquote(value.password or ''), database=database)
    ca = parse_qs(value.query).get('ssl_ca', [None])[0]
    if ca: result['ssl_ca'] = ca
    return result


def identity(uri):
    value = options(uri)
    return (value['host'].lower(), value['port'], value['database'])


def run_tool(tool, uri, arguments, directory, sql_file, restore=False):
    connection = options(uri)
    config = Path(directory) / 'client.cnf'
    lines = ['[client]']
    for name in ('host', 'port', 'user', 'password'):
        lines.append(name + '=' + json.dumps(str(connection[name])))
    if connection.get('ssl_ca'):
        lines.extend(['ssl-mode=VERIFY_IDENTITY', 'ssl-ca=' + json.dumps(connection['ssl_ca'])])
    config.write_text('\n'.join(lines) + '\n')
    config.chmod(0o600)
    try:
        with Path(sql_file).open('rb' if restore else 'wb') as stream:
            result = subprocess.run([tool, '--defaults-extra-file=' + str(config), *arguments, connection['database']], stdin=stream if restore else subprocess.DEVNULL, stdout=subprocess.DEVNULL if restore else stream, stderr=subprocess.PIPE, timeout=int(os.environ.get('BACKUP_TOOL_TIMEOUT_SECONDS', '3600')))
        if result.returncode: raise RuntimeError(Path(tool).name + ' failed; verify permissions and client version')
    finally:
        config.unlink(missing_ok=True)
