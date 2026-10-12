"""Actual Apache HTTPS regression: private PDFs can frame only on the same site."""
import io
import os
import socket
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.skipif(not os.environ.get('APACHE_TEST_BINARY'), reason='Requires native Apache on Linux')


def test_apache_pdf_framing_policy(tmp_path):
    import grp
    import pwd
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pypdf import PdfWriter

    root = Path(__file__).resolve().parents[2]
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.end_headers()
            self.wfile.write(pdf.getvalue())

        def log_message(self, *_):
            pass

    backend = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
                   .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
                   .sign(key, hashes.SHA256()))
    (tmp_path/'qa.key').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (tmp_path/'qa.crt').write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    (tmp_path/'index.html').write_text('<html>Apache preview test</html>')
    modules = ['mpm_event','authz_core','authz_host','dir','mime','proxy','proxy_http','headers','rewrite','ssl','socache_shmcb']
    loads = '\n'.join(f'LoadModule {module}_module /usr/lib/apache2/modules/mod_{module}.so' for module in modules)
    snippet = (root/'deploy/aapanel-apache.conf').read_text().replace('/www/wwwroot/big-mobile/current/frontend/build', str(tmp_path)).replace('127.0.0.1:8000', f'127.0.0.1:{backend.server_port}')
    config = tmp_path/'httpd.conf'
    config.write_text(f'''ServerRoot /etc/apache2
DefaultRuntimeDir "{tmp_path}"
PidFile "{tmp_path}/httpd.pid"
Listen 127.0.0.1:{port}
ServerName localhost
User {pwd.getpwuid(os.getuid()).pw_name}
Group {grp.getgrgid(os.getgid()).gr_name}
ErrorLog "{tmp_path}/apache-error.log"
TypesConfig /etc/mime.types
DirectoryIndex index.html
{loads}
<VirtualHost 127.0.0.1:{port}>
DocumentRoot "{tmp_path}"
SSLEngine on
SSLCertificateFile "{tmp_path}/qa.crt"
SSLCertificateKeyFile "{tmp_path}/qa.key"
{snippet}
</VirtualHost>
''')
    output = (tmp_path/'apache-start.log').open('w')
    process = subprocess.Popen([os.environ['APACHE_TEST_BINARY'], '-DFOREGROUND', '-f', str(config)], stdout=output, stderr=output)
    try:
        import time
        origin = f'https://localhost:{port}'
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError((tmp_path/'apache-start.log').read_text())
            try:
                home = requests.get(origin+'/', verify=str(tmp_path/'qa.crt'), timeout=2)
                if home.status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('Apache did not become ready')
        assert home.headers['X-Frame-Options'] == 'DENY'
        assert "frame-ancestors 'none'" in home.headers['Content-Security-Policy']
        preview = requests.get(origin+'/api/files/proof.pdf', verify=str(tmp_path/'qa.crt'), timeout=5)
        assert preview.status_code == 200 and preview.content == pdf.getvalue()
        assert preview.headers['X-Frame-Options'] == 'SAMEORIGIN'
        policy = preview.headers['Content-Security-Policy']
        assert "frame-ancestors 'self'" in policy
        assert "frame-ancestors 'none'" not in policy and policy.count('frame-ancestors') == 1
        other = requests.get(origin+'/api/health', verify=str(tmp_path/'qa.crt'), timeout=5)
        assert other.headers['X-Frame-Options'] == 'DENY'
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        output.close()
        backend.shutdown()
        backend.server_close()
        thread.join(timeout=5)
