#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ -z $(git -C "$ROOT" status --porcelain) ]] || die "Checkout must be clean."
[[ $(git -C "$ROOT" branch --show-current) == main || $(git -C "$ROOT" branch --show-current) == ops/a1-minimum-production-deploy ]] || die "Unexpected deployment branch."
git -C "$ROOT" fetch --all --prune
branch=$(git -C "$ROOT" branch --show-current)
[[ $(git -C "$ROOT" rev-parse HEAD) == $(git -C "$ROOT" rev-parse "origin/$branch") ]] || die "Checkout differs from remote; synchronize approved commit first."
compose config --quiet
install -d -m 700 "$STATE"
if [[ -f $STATE/current-commit && $(cat "$STATE/current-commit") != "$GOROFAN_DEPLOY_SHA" ]]; then
  cp "$STATE/current-commit" "$STATE/previous-commit"
fi
printf '%s\n' "$GOROFAN_DEPLOY_SHA" > "$STATE/attempted-commit"
[[ ! -f /srv/gorofan/data/app.db ]] || bash "$ROOT/deploy/a1/backup.sh"
# Keep builds sequential on small A1 shapes, before stopping the working app.
compose build backend
compose build frontend
# Quiesce only this project before schema changes; never touch unrelated services.
compose stop frontend backend
compose run --rm --no-deps backend alembic upgrade head
compose run --rm --no-deps backend python -c 'import sqlite3; db=sqlite3.connect("/app/data/app.db"); assert db.execute("select version_num from alembic_version").fetchall()==[("0003_edit_diff_capture",)]'
compose up -d --no-build --wait --wait-timeout 180 backend frontend
bash "$ROOT/deploy/a1/check.sh"
printf '%s\n' "$GOROFAN_DEPLOY_SHA" > "$STATE/current-commit"
echo "Deployed exact commit: $GOROFAN_DEPLOY_SHA"
