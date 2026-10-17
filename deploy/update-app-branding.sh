#!/usr/bin/env bash
# Incremental aaPanel/Apache branding update, preserving settings and uploads.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/78515de43f3cfc208c1b9ba0ce83743548bcf65d
files=(
  backend/server.py
  backend/app_branding.py
  frontend/index.html
  frontend/public/manifest.json
  frontend/src/context/BrandingContext.jsx
  frontend/src/lib/branding.js
  frontend/src/pages/admin/AdminLayout.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
.venv/bin/python -m py_compile "$stage/new/backend/server.py" "$stage/new/backend/app_branding.py"
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
    curl --max-time 10 --fail --silent http://127.0.0.1:8000/api/branding/manifest.webmanifest
    printf '\nUpdate berhasil. Muat ulang Chrome sebelum membuat pintasan baru.\n'
    exit 0
  fi
  sleep 2
done
journalctl -u big-mobile -n 40 --no-pager
exit 1
