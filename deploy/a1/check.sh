#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
compose ps
for service in backend frontend; do
  id=$(compose ps -q "$service")
  [[ -n $id ]] || die "$service missing."
  [[ $(docker inspect -f '{{.State.Running}} {{.State.Health.Status}}' "$id") == 'true healthy' ]] || die "$service not healthy."
done
curl -fsS --max-time 10 http://127.0.0.1:8000/healthz; echo
curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:3000/
# Browser-facing same-origin rewrite proves frontend -> backend reachability.
curl -fsS --max-time 10 http://127.0.0.1:3000/api/v1/auth/me >/dev/null
df -h /srv/gorofan
free -h
docker stats --no-stream $(compose ps -q backend frontend)
python3 - <<'PY'
from pathlib import Path
import time
files = list(Path('/srv/gorofan/backups').glob('gorofan-*.tar.gz'))
if not files:
    print('WARNING: no DB backup yet')
else:
    age = time.time() - max(p.stat().st_mtime for p in files)
    print(f'Latest local DB backup age: {age / 3600:.1f} hours')
    if age > 86400:
        print('WARNING: DB backup older than 24 hours')
marker = Path('/srv/gorofan/backups/last-off-instance-upload')
pc = Path('/srv/gorofan/backups/last-managed-pc-copy')
print('Off-instance hook upload: ' + (marker.read_text().strip() if marker.exists() else 'not configured'))
print('Verified managed-PC copy: ' + (pc.read_text().strip() if pc.exists() else 'UNVERIFIED'))
if not marker.exists() and not pc.exists():
    print('RECOVERY BLOCKER: no verified off-instance transfer receipt')
for receipt in (marker, pc):
    if receipt.exists() and time.time() - receipt.stat().st_mtime > 86400:
        print(f'WARNING: {receipt.name} older than 24 hours; transfer a fresh backup')
PY
echo 'Backend + frontend + frontend API proxy checks passed.'
