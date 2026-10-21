#!/usr/bin/env bash
# aaPanel update: POST deletion compatibility and assignment-only print output.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/c16dbb03e274943ff898dfee1a32cb2e94b78351
files=(
  backend/server.py
  backend/database.py
  backend/idempotency.py
  backend/record_deletion.py
  backend/admin_reports.py
  backend/app_branding.py
  backend/whatsapp.py
  frontend/src/components/DeleteDataButton.jsx
  frontend/src/pages/admin/Klien.jsx
  frontend/src/pages/admin/SuratKuasa.jsx
  frontend/src/pages/admin/AkunUnit.jsx
  frontend/src/pages/admin/Petugas.jsx
  frontend/src/pages/admin/Penugasan.jsx
  frontend/src/pages/admin/SuratTugas.jsx
  frontend/src/pages/admin/SuratPenugasanDoc.jsx
  frontend/src/pages/admin/LaporanPetugas.jsx
  frontend/src/pages/admin/LaporanDetail.jsx
  frontend/src/pages/admin/PembayaranLeasing.jsx
  frontend/src/pages/admin/PKS.jsx
  frontend/src/pages/admin/PenggunaAdmin.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
.venv/bin/python -m py_compile "$stage/new/backend/server.py" "$stage/new/backend/database.py" "$stage/new/backend/idempotency.py" "$stage/new/backend/record_deletion.py" "$stage/new/backend/admin_reports.py" "$stage/new/backend/app_branding.py" "$stage/new/backend/whatsapp.py"
printf 'Salinan kode lama disimpan di: %s/backup\n' "$stage"
for file in "${files[@]}"; do
  mkdir -p "$stage/backup/$(dirname "$file")"
  if [ -f "$file" ]; then cp -p "$file" "$stage/backup/$file"; fi
  install -m 644 "$stage/new/$file" "$file"
done
REACT_APP_BACKEND_URL='' npm --prefix frontend run build
systemctl restart big-mobile
for attempt in $(seq 1 30); do
  if curl --max-time 10 --fail --silent http://127.0.0.1:8000/api/health; then
    printf '\n'
    .venv/bin/python <<'CHECK'
import json
import os
import urllib.error
import urllib.request
from dotenv import load_dotenv
load_dotenv('/etc/big-mobile/app.env', override=True)
origins=['http://127.0.0.1:8000']
public=os.environ.get('APP_BASE_URL','').rstrip('/')
if public:origins.append(public)
menus=('clients','surat-kuasa','akun','petugas','penugasan','surat-tugas','laporan','leasing-payments','pks','admin-users')
for origin in origins:
    for menu in menus:
        path=f'/api/{menu}/__route_check__/delete'
        request=urllib.request.Request(origin+path,data=json.dumps({'reason':'Pemeriksaan route tanpa sesi'}).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            response=urllib.request.urlopen(request,timeout=15)
            code=response.status
            response.close()
        except urllib.error.HTTPError as error:
            code=error.code
        except Exception as error:
            raise SystemExit(f'Pemeriksaan route gagal ({type(error).__name__}): {origin}{path}. Periksa koneksi/proxy server.')
        if code!=401:
            raise SystemExit(f'Route hapus belum valid: {origin}{path} memberikan HTTP {code}, seharusnya 401 tanpa login. Periksa service/proxy Apache.')
print('Seluruh route hapus aktif dan menolak permintaan tanpa login. Tidak ada record yang dihapus oleh pemeriksaan ini.')
CHECK
    printf '\nUpdate berhasil. Muat ulang browser. Output surat tidak lagi melampirkan halaman BASTK.\n' 
    exit 0
  fi
  sleep 2
done
journalctl -u big-mobile -n 40 --no-pager
exit 1
