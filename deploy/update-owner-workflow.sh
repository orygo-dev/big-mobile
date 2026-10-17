#!/usr/bin/env bash
# Incremental aaPanel update; keeps configuration, uploaded files and old assignments.
set -euo pipefail
cd /www/wwwroot/big.rebornpartner.xyz

stage=$(mktemp -d)
base=https://raw.githubusercontent.com/orygo-dev/big-mobile/9ceb421b18af00ba4d717742fea89c7d5bbf16dd
files=(
  backend/server.py
  backend/owner_workflow.py
  backend/manage.py
  backend/chat.py
  backend/admin_reports.py
  frontend/src/App.jsx
  frontend/src/components/ProtectedRoute.jsx
  frontend/src/components/FieldAssignmentLetter.jsx
  frontend/src/components/PenugasanDialog.jsx
  frontend/src/components/ApprovalBadge.jsx
  frontend/src/lib/constants.js
  frontend/src/pages/AssignmentChat.jsx
  frontend/src/pages/ChatInbox.jsx
  frontend/src/pages/Login.jsx
  frontend/src/pages/admin/AdminLayout.jsx
  frontend/src/pages/admin/Dashboard.jsx
  frontend/src/pages/admin/Penugasan.jsx
  frontend/src/pages/admin/SuratPenugasanDoc.jsx
  frontend/src/pages/admin/PenggunaAdmin.jsx
)
for file in "${files[@]}"; do
  mkdir -p "$stage/new/$(dirname "$file")"
  curl --fail --silent --show-error --location "$base/$file" -o "$stage/new/$file"
done
.venv/bin/python -m py_compile "$stage/new/backend/server.py" "$stage/new/backend/owner_workflow.py" "$stage/new/backend/manage.py" "$stage/new/backend/chat.py" "$stage/new/backend/admin_reports.py"
printf 'Salinan kode lama disimpan di: %s/backup\n' "$stage"
for file in "${files[@]}"; do
  mkdir -p "$stage/backup/$(dirname "$file")"
  if [ -f "$file" ]; then cp -p "$file" "$stage/backup/$file"; fi
  install -m 644 "$stage/new/$file" "$file"
done
REACT_APP_BACKEND_URL='' npm --prefix frontend run build

# getpass asks privately only if this owner does not already exist.
# For automation, BOOTSTRAP_OWNER_PASSWORD may be supplied via the environment.
.venv/bin/python backend/manage.py bootstrap-owner --env /etc/big-mobile/app.env \
  --name Owner --email owner@rebornpartner.xyz \
  --admin-email "${OWNER_ADMIN_EMAIL:-admin@rebornpartner.xyz}"

systemctl restart big-mobile
for attempt in $(seq 1 30); do
  if curl --max-time 10 --fail --silent http://127.0.0.1:8000/api/health; then
    printf '\nUpdate berhasil. Login owner: owner@rebornpartner.xyz\n'
    exit 0
  fi
  sleep 2
done
journalctl -u big-mobile -n 40 --no-pager
exit 1
