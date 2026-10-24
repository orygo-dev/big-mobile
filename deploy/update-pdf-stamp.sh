#!/usr/bin/env bash
# aaPanel / Apache: build first, retain originals and restore code on failure.
set -euo pipefail
root=/www/wwwroot/big.rebornpartner.xyz
cd "$root"
test "$(pwd -P)" = "$root" || { echo 'Root project tidak sesuai.'; exit 1; }
test -x .venv/bin/python && test -f frontend/package.json
command -v npm >/dev/null
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/c03fe38b41dd116dc65c12d4a9ed2e39b063325c
files=(
  backend/server.py
  backend/pdf_stamp.py
  backend/requirements-production.txt
  backend/requirements-production.lock
  frontend/package.json
  frontend/package-lock.json
  frontend/vite.config.mjs
  frontend/src/components/PdfStampEditor.jsx
  frontend/src/pages/admin/AkunUnit.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")" "$stage/backup/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
  if [ -f "$file" ]; then cp -p "$file" "$stage/backup/$file"; fi
done
.venv/bin/python -m py_compile "$stage/new/backend/server.py" "$stage/new/backend/pdf_stamp.py"
if [ -f frontend/build/index.html ]; then cp -p frontend/build/index.html "$stage/old-index.html"; fi
changed=0
restarted=0
rollback() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$changed" -eq 1 ]; then
    echo 'Pembaruan belum berhasil. Mengembalikan kode sebelumnya.'
    for file in "${files[@]}"; do
      if [ -f "$stage/backup/$file" ]; then cp -p "$stage/backup/$file" "$file"; fi
    done
    if [ -f "$stage/old-index.html" ]; then cp -p "$stage/old-index.html" frontend/build/index.html; fi
    if [ "$restarted" -eq 1 ]; then systemctl restart big-mobile || true; fi
    printf 'Log/build dan salinan lama tersimpan di: %s\n' "$stage"
  fi
  exit "$rc"
}
trap rollback EXIT
printf 'Salinan kode lama: %s/backup\n' "$stage"
changed=1
for file in "${files[@]}"; do
  mkdir -p "$(dirname "$file")"
  install -m 644 "$stage/new/$file" "$file"
done
.venv/bin/python -m pip install --require-hashes -r backend/requirements-production.lock
npm --prefix frontend ci --legacy-peer-deps
REACT_APP_BACKEND_URL='' npm --prefix frontend run build -- --outDir "$stage/build"
test -s "$stage/build/index.html"
# Protected aaPanel .user.ini remains untouched. Assets are published before HTML.
mkdir -p frontend/build
for item in "$stage/build"/*; do
  if [ "$(basename "$item")" != index.html ]; then cp -a "$item" frontend/build/; fi
done
restarted=1
systemctl restart big-mobile
ready=0
for attempt in $(seq 1 30); do
  if curl --max-time 5 --fail --silent http://127.0.0.1:8000/api/health; then ready=1; printf '\n'; break; fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then journalctl -u big-mobile -n 40 --no-pager; exit 1; fi
# Probe only localhost with no credentials or real record ID; never edits data.
code=$(curl --max-time 10 --silent --output "$stage/route-check.json" --write-out '%{http_code}' http://127.0.0.1:8000/api/surat-kuasa/route-check/stamp-info)
if [ "$code" != 401 ]; then echo "Endpoint editor belum siap (HTTP $code)."; exit 1; fi
install -m 644 "$stage/build/index.html" frontend/build/index.html
trap - EXIT
printf '\nPembaruan berhasil. Tekan Ctrl+F5, lalu Kontrak & Unit > Lihat dokumen > Tambahkan Tanda Tangan/Stempel.\n'
printf 'PDF asli dan riwayat versi tetap tersimpan. Backup kode: %s/backup\n' "$stage"
