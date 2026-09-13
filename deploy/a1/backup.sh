#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
base=/srv/gorofan/backups
install -d -m 700 "$base"
umask 077
work=$(mktemp -d "$base/.snapshot.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
# SQLite online backup API, never a raw copy of a live DB (WAL-safe).
python3 - "$work/app.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect('file:/srv/gorofan/data/app.db?mode=ro', uri=True)
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)
assert dst.execute('PRAGMA integrity_check').fetchone() == ('ok',)
assert dst.execute('select version_num from alembic_version').fetchall() == [('0003_edit_diff_capture',)]
dst.close()
src.close()
PY
printf '%s\n' "$GOROFAN_DEPLOY_SHA" > "$work/source-commit"
cp -a /srv/gorofan/data/media "$work/media"
# Include additional persistent files, excluding SQLite live files and media.
tar -C /srv/gorofan/data --exclude='./app.db' --exclude='./app.db-*' --exclude='./media' -czf "$work/extra-data.tar.gz" .
archive="$base/gorofan-$(date -u +%Y%m%dT%H%M%SZ)-${work##*.}.tar.gz"
tar -C "$work" -czf "$archive" .
chmod 600 "$archive"
tar -tzf "$archive" >/dev/null
echo "Backup verified: $archive"
# Optional root-owned executable hook receives one archive path. No eval.
# Configure secure external transfer there; credentials remain outside Git.
hook=/etc/gorofan/backup-upload
if [[ -e $hook ]]; then
  [[ -f $hook && ! -L $hook && -x $hook && $(stat -c %u "$hook") == 0 ]] || die "Invalid upload hook."
  [[ $(stat -c %a "$hook") == 700 ]] || die "Upload hook must be mode 700."
  "$hook" "$archive"
  date -u +%FT%TZ > "$base/last-off-instance-upload"
else
  echo 'RECOVERY BLOCKER: no off-instance upload hook; securely pull this archive to a managed PC/backup host.' >&2
fi
