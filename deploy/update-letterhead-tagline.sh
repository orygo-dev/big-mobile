#!/usr/bin/env bash
# aaPanel frontend update: company letterhead tagline.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/307e44ce307595120ae3c9a4bbaefe6fde74cd30
files=(
  frontend/src/components/CompanyLetterhead.jsx
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
printf 'Update selesai. Muat ulang browser; Kop surat kini memuat PROFESIONAL COLLECTION.\n'
