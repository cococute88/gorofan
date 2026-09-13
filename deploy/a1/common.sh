#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
ENV_FILE=/etc/gorofan/gorofan.env
STATE=/srv/gorofan/state
die() { echo "ERROR: $*" >&2; exit 1; }
[[ $EUID == 0 ]] || die "Run with sudo (external env is root-readable only)."
[[ -f $ENV_FILE && ! -L $ENV_FILE ]] || die "Restore/create $ENV_FILE before deployment."
[[ $(stat -c %a "$ENV_FILE") == 600 && $(stat -c %u "$ENV_FILE") == 0 ]] || die "Env must be root-owned mode 600."
docker compose version >/dev/null
version=$(docker compose version --short | sed 's/^v//; s/-.*//')
[[ $(printf '2.24.4\n%s\n' "$version" | sort -V | head -1) == 2.24.4 ]] || die "Compose >=2.24.4 required."
# Never source env as shell code or print compose config containing secrets.
secret=$(sed -n 's/^APP_SECRET_KEY=//p' "$ENV_FILE")
[[ $secret =~ ^[a-f0-9]{64}$ ]] || die "APP_SECRET_KEY must be one 64-character random hex value."
unset secret
export GOROFAN_DEPLOY_SHA=${GOROFAN_DEPLOY_SHA:-$(git -C "$ROOT" rev-parse HEAD)}
compose() {
  docker compose --project-name gorofan --env-file "$ENV_FILE" \
    -f "$ROOT/docker-compose.yml" -f "$ROOT/deploy/a1/docker-compose.prod.yml" "$@"
}
