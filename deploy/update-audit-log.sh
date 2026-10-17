#!/usr/bin/env bash
# aaPanel frontend update: dedicated Audit Log page.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/71d7f27a9b90653a22ea3c35b3a0b675042dfbaa
files=(
  frontend/src/App.jsx
  frontend/src/pages/admin/AdminLayout.jsx
  frontend/src/pages/admin/Pengaturan.jsx
  frontend/src/pages/admin/AuditLog.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
printf 'Salinan kode lama disimpan di: %s/backup\n' "$stage"
for file in "${files[@]}"; do
  mkdir -p "$stage/backup/$(dirname "$file")"
  if [ -f "$file" ]; then cp -p "$file" "$stage/backup/$file"; fi
  install -m 644 "$stage/new/$file" "$file"
done
# Preserve aaPanel .user.ini using the existing Vite configuration.
REACT_APP_BACKEND_URL='' npm --prefix frontend run build
printf 'Update selesai. Muat ulang browser; Audit Log tersedia di bawah Pengaturan.\n'
