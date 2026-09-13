#!/usr/bin/env bash
# Run explicitly with --init-secret ONLY for a fresh production database.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 && $(uname -m) == aarch64 ]] || {
  echo 'Supported baseline: Ubuntu 24.04 AArch64.' >&2; exit 1;
}
init=false
swap=false
for arg in "$@"; do
  case "$arg" in
    --init-secret) init=true ;;
    --with-swap) swap=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y git curl sqlite3 python3
systemctl enable --now docker
for path in /etc/gorofan /srv/gorofan /srv/gorofan/data /srv/gorofan/backups /srv/gorofan/state; do
  [[ ! -L $path ]] || { echo "Refusing symlink: $path" >&2; exit 1; }
done
install -d -m 700 /etc/gorofan /srv/gorofan /srv/gorofan/backups /srv/gorofan/state
install -d -m 700 /srv/gorofan/data /srv/gorofan/data/media
if [[ ! -e /etc/gorofan/gorofan.env ]]; then
  $init || { echo 'Restore production env, or use --init-secret for a fresh DB.' >&2; exit 1; }
  [[ -z $(find /srv/gorofan/data -type f -print -quit) ]] || {
    echo 'Existing data: restore original secret; refusing to regenerate.' >&2; exit 1;
  }
  umask 077
  python3 - <<'PY'
import secrets
with open('/etc/gorofan/gorofan.env', 'x') as f:
    f.write('APP_SECRET_KEY=' + secrets.token_hex(32) + '\n')
    f.write('APP_ENV=prod\nAUTH_ENABLED=false\n')
PY
fi
if $swap && [[ -z $(swapon --show --noheadings) ]]; then
  install -d -m 700 /var/lib/gorofan
  path=/var/lib/gorofan/build.swap
  [[ ! -L $path ]] || { echo 'Swap symlink refused.' >&2; exit 1; }
  if [[ ! -e $path ]]; then
    [[ $(df --output=avail -B1 /var/lib/gorofan | tail -1) -gt 4294967296 ]] || {
      echo 'Insufficient free disk for build swap.' >&2; exit 1;
    }
    fallocate -l 2G "$path"
    chmod 600 "$path"
    mkswap "$path"
  fi
  swapon "$path"
  grep -q '^/var/lib/gorofan/build.swap ' /etc/fstab || \
    printf '/var/lib/gorofan/build.swap none swap sw 0 0\n' >> /etc/fstab
fi
echo 'Bootstrap complete. Secret never printed; retain it securely off-instance.'
