#!/usr/bin/env bash
set -euo pipefail
# Run from repository root on the aaPanel host.
release_tag="${1:?Usage: deploy/release.sh RELEASE_TAG}"
[[ "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]] || exit 2
base=/www/wwwroot/big-mobile
release="$base/releases/$release_tag"
test -f /etc/big-mobile/app.env
test ! -e "$release"
mkdir -p "$release"
git archive HEAD | tar -x -C "$release"
"${PYTHON_BIN:-python3.12}" -m venv "$release/.venv"
"$release/.venv/bin/pip" install --require-hashes -r "$release/backend/requirements-production.lock"
(cd "$release/frontend"; npm ci --legacy-peer-deps; REACT_APP_BACKEND_URL='' npm run build)
"$release/.venv/bin/python" "$release/backend/manage.py" --env /etc/big-mobile/app.env preflight
previous=$(readlink "$base/current" || true)
ln -s "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl restart big-mobile
for attempt in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8000/api/health; then printf '\nRelease %s ready.\n' "$release_tag"; exit 0; fi
    sleep 2
done
if [[ -n "$previous" ]]; then ln -s "$previous" "$base/current.next"; mv -Tf "$base/current.next" "$base/current"; systemctl restart big-mobile; fi
exit 1
