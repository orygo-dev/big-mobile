#!/usr/bin/env bash
set -euo pipefail
release_tag="${1:?Usage: deploy/rollback.sh PREVIOUS_RELEASE_TAG}"
[[ "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]] || exit 2
base=/www/wwwroot/big-mobile
release="$base/releases/$release_tag"
test -x "$release/.venv/bin/python"
test -f "$release/frontend/build/index.html"
"$release/.venv/bin/python" "$release/backend/manage.py" --env /etc/big-mobile/app.env preflight
ln -s "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl restart big-mobile
for attempt in $(seq 1 30); do curl --fail --silent http://127.0.0.1:8000/api/health && exit 0; sleep 2; done
exit 1
