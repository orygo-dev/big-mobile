#!/usr/bin/env bash
# Stabilize only the existing PDF editor frontend; no backend/database changes.
set -euo pipefail
root=/www/wwwroot/big.rebornpartner.xyz
cd "$root"
test "$(pwd -P)" = "$root" || { echo 'Root project tidak sesuai.'; exit 1; }
test -f frontend/package.json
test -d frontend/node_modules/pdfjs-dist || { echo 'Dependensi editor PDF belum tersedia. Jalankan pembaruan fitur PDF terlebih dahulu.'; exit 1; }
command -v npm >/dev/null
stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/9b27932fdf5cf067289ad820b75ea06ef9bc1bfb
files=(
  frontend/src/components/PdfStampEditor.jsx
  frontend/src/pages/admin/AkunUnit.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")" "$stage/backup/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
  cp -p "$file" "$stage/backup/$file"
done
if [ -f frontend/build/index.html ]; then cp -p frontend/build/index.html "$stage/old-index.html"; fi
changed=0
rollback() {
  rc=$?
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$changed" -eq 1 ]; then
    for file in "${files[@]}"; do cp -p "$stage/backup/$file" "$file"; done
    if [ -f "$stage/old-index.html" ]; then cp -p "$stage/old-index.html" frontend/build/index.html; fi
    printf 'Pembaruan gagal; kode sebelumnya dipulihkan. Backup/log: %s\n' "$stage"
  fi
  exit "$rc"
}
trap rollback EXIT
printf 'Backup kode: %s/backup\n' "$stage"
changed=1
for file in "${files[@]}"; do install -m 644 "$stage/new/$file" "$file"; done
REACT_APP_BACKEND_URL='' npm --prefix frontend run build -- --outDir "$stage/build"
test -s "$stage/build/index.html"
mkdir -p frontend/build
for item in "$stage/build"/*; do
  if [ "$(basename "$item")" != index.html ]; then cp -a "$item" frontend/build/; fi
done
install -m 644 "$stage/build/index.html" frontend/build/index.html
trap - EXIT
printf '\nPembaruan tampilan berhasil. Tekan Ctrl+F5, lalu buka kembali editor tanda tangan/stempel.\n'
