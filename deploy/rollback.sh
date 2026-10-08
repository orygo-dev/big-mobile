#!/usr/bin/env bash
set -euo pipefail
release_tag="${1:?Usage: deploy/rollback.sh PREVIOUS_RELEASE_TAG}"
[[ "$release_tag" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]] || exit 2
export RELEASE_TAG="$release_tag"
# Existing immutable local release images only; never restore database over live data.
docker image inspect "big-mobile-api:$release_tag" >/dev/null
docker image inspect "big-mobile-web:$release_tag" >/dev/null
docker compose -f deploy/compose.yml up -d --no-build --wait --wait-timeout 180
curl --fail --silent http://127.0.0.1:8080/api/health
