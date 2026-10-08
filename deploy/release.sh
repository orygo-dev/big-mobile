#!/usr/bin/env bash
set -euo pipefail
# Run from repository root on the aaPanel host.
release_tag="${1:?Usage: deploy/release.sh RELEASE_TAG}"
[[ "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]] || exit 2
test -f deploy/app.env
chmod 600 deploy/app.env
export RELEASE_TAG="$release_tag"
docker compose -f deploy/compose.yml config --quiet
docker compose -f deploy/compose.yml build --pull
docker compose -f deploy/compose.yml run --rm --no-deps backend python manage.py preflight
docker compose -f deploy/compose.yml up -d --wait --wait-timeout 180
curl --fail --silent http://127.0.0.1:8080/api/health
printf '\nRelease %s passed local readiness. Verify HTTPS before switching traffic.\n' "$release_tag"
