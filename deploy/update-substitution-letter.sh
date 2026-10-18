#!/usr/bin/env bash
# aaPanel update: substitution letter heading and official numbering.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/f1efcdace168afbd81ffa5e534dd732454113cd6
files=(
  backend/server.py
  backend/seed.py
  frontend/src/components/CompanyLetterhead.jsx
  frontend/src/components/FieldAssignmentLetter.jsx
  frontend/src/pages/admin/Pengaturan.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
.venv/bin/python -m py_compile "$stage/new/backend/server.py" "$stage/new/backend/seed.py"
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
    printf '\nUpdate berhasil. Nomor baru memakai 3 digit dan bulan Romawi. Atur Kode Perusahaan menjadi BIG-SKS bila sesuai.\n'
    exit 0
  fi
  sleep 2
done
journalctl -u big-mobile -n 40 --no-pager
exit 1
