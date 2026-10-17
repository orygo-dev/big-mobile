#!/usr/bin/env bash
# aaPanel/Apache incremental update, without additional services.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
[ -x .venv/bin/python ] || { echo 'Virtualenv project tidak ditemukan.'; exit 1; }
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/fd256b2787ffb7ea3d66641d2cb39c6dbaf1c384
files=(
  backend/database.py
  backend/server.py
  backend/admin_reports.py
  backend/owner_workflow.py
  backend/whatsapp.py
  frontend/src/components/FonnteSettings.jsx
  frontend/src/pages/admin/Pengaturan.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
.venv/bin/python -m py_compile "$stage/new/backend/database.py" "$stage/new/backend/server.py" "$stage/new/backend/admin_reports.py" "$stage/new/backend/owner_workflow.py" "$stage/new/backend/whatsapp.py"
printf 'Salinan kode lama disimpan di: %s/backup\n' "$stage"
for file in "${files[@]}"; do
  mkdir -p "$stage/backup/$(dirname "$file")"
  if [ -f "$file" ]; then cp -p "$file" "$stage/backup/$file"; fi
  install -m 644 "$stage/new/$file" "$file"
done
# Existing Vite configuration preserves aaPanel's protected .user.ini.
REACT_APP_BACKEND_URL='' npm --prefix frontend run build
systemctl restart big-mobile
for attempt in $(seq 1 30); do
  if curl --max-time 10 --fail --silent http://127.0.0.1:8000/api/health; then
    printf '\nUpdate berhasil. Buka Pengaturan > Notifikasi WhatsApp Fonnte.\n'
    exit 0
  fi
  sleep 2
done
journalctl -u big-mobile -n 40 --no-pager
exit 1
