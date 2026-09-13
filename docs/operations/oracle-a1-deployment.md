# Oracle A1 minimum production deployment

This is a single personal Ubuntu 24.04 AArch64 server deployment. Application
logic follows main containing PR #33 merge `af63eabc961a4a4f2fbdc4bd118181aed8d4fcaa`.
Deployment assets initially run from `ops/a1-minimum-production-deploy`; after
review/merge, synchronize and redeploy approved main. The authoritative running
SHA is `/srv/gorofan/state/current-commit`, corroborated by image tags and the
checkout's `git rev-parse HEAD`. Do not infer it from this document's revision.

## Architecture and access

Reuse root `docker-compose.yml` with `deploy/a1/docker-compose.prod.yml`.
Compose >=2.24.4 is required to replace development ports using `!override`.
Project/network names are isolated under `gorofan`. Never start the offline
profile/Ollama. No Kubernetes, CI deploy, proxy, or extra supervisor is required.

| Purpose | Location / behavior |
| --- | --- |
| Checkout | `/opt/gorofan` |
| External production environment | `/etc/gorofan/gorofan.env`, root-owned 600 |
| SQLite | `/srv/gorofan/data/app.db` -> `/app/data/app.db` |
| Media | `/srv/gorofan/data/media` -> `/app/data/media` |
| Local backup staging | `/srv/gorofan/backups`, root-owned 700 |
| Deployment state | `/srv/gorofan/state/{current,previous,attempted}-commit` |
| Backend host socket | `127.0.0.1:8000` |
| Frontend host socket | `127.0.0.1:3000` |
| Browser API | `/api/v1`, same origin as frontend |
| Frontend build-time rewrite | `/api/*` -> `http://backend:8000/api/*` |
| Process recovery | Docker enabled; both services `unless-stopped` |

Use your existing SSH host/identity; no real address or credential belongs here:

```sh
ssh -N -L 3000:127.0.0.1:3000 <existing-a1-ssh-host>
# Browse http://localhost:3000
# Optional diagnostics: add -L 8000:127.0.0.1:8000
```

If you use an explicit existing key instead of an SSH alias, add `-i <key-path>`
and `<existing-user>@<current-server-address>`. Bind the tunnel to localhost.
Using another local frontend port still works because API requests are same
origin; update CORS before making direct cross-origin backend requests.

AUTH is deliberately disabled for this SSH-only personal baseline. Do not
publish the root Compose or change host sockets to 0.0.0.0. Container 0.0.0.0
listening is necessary for Docker networking and is distinct from host binding.
No Gemini credential is installed and no live generation is part of deployment.

## First deployment

Read inventory first: OS, `uname -m`, `nproc`, `free -h`, `df -h`, `lsblk`,
`ss -lntp`, containers, systemd services, and OS firewall. Preserve unrelated
services and firewall rules. OCI Security Lists/NSGs are separate from the OS
firewall; do not assume one proves the other's configuration.

```sh
sudo git clone https://github.com/cococute88/gorofan.git /opt/gorofan
cd /opt/gorofan
sudo git fetch --all --prune
sudo git checkout ops/a1-minimum-production-deploy # main after review/merge
sudo git pull --ff-only
sudo git status --short
sudo git rev-parse HEAD # compare with the approved exact commit
sudo bash deploy/a1/bootstrap.sh --init-secret --with-swap
sudo bash deploy/a1/deploy.sh
sudo bash deploy/a1/backup.sh
```

`--init-secret` is only for a fresh DB. Bootstrap refuses secret creation when
data exists, and never overwrites an existing environment. It generates a
cryptographically random 32-byte hex secret without printing it. Recoveries
must restore the original env instead. No local development DB is uploaded.

Bootstrap uses Ubuntu's ARM64 Docker/Compose packages. Images use the upstream
multi-arch Python 3.12 slim and Node 20 alpine bases. Native Python dependencies
(cryptography, asyncpg, pydantic-core, uvloop, httptools, watchfiles) are validated
by the actual A1 image build; there is no hard-coded x86 wheel. The frontend uses
the checked-in npm lockfile and a single Next build worker. On a 1 GiB server,
optional 2 GiB disk swap prevents real build OOM; it does not reserve fake RAM
or generate workload. Never prune other projects' Docker assets.

Deployment validates a clean checkout equal to its remote branch, builds images
sequentially, stops only this project's services, runs Alembic, checks exact
`0003_edit_diff_capture`, then starts both services with health checks. Migration
failure exits before app start. The backend image also uses
`alembic upgrade head && uvicorn ... --workers 1`, including on restart.

## Operation, update, and restart

```sh
cd /opt/gorofan
sudo bash deploy/a1/check.sh
sudo bash -c 'source deploy/a1/common.sh; compose ps'
sudo bash -c 'source deploy/a1/common.sh; compose logs --tail 100 backend'
sudo bash -c 'source deploy/a1/common.sh; compose logs --tail 100 frontend'
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS -o /dev/null http://127.0.0.1:3000/
curl -fsS http://127.0.0.1:3000/api/v1/auth/me
df -h /srv/gorofan
free -h
sudo bash -c 'source deploy/a1/common.sh; compose restart backend frontend'
```

Logs rotate at 3 x 10 MiB per service. Do not print `compose config` without
`--quiet`, inspect full container environment, echo secrets, or enable shell
tracing around configuration. `check.sh` checks both Docker health states,
backend HTTP, frontend HTTP/API proxy, disk/memory, and backup age.

Update only an approved branch/commit, with no local changes:

```sh
cd /opt/gorofan
sudo git fetch --all --prune
sudo git status --short
sudo git checkout main # only once deployment assets have merged
sudo git pull --ff-only
sudo git rev-parse HEAD # record approved main SHA
sudo bash deploy/a1/deploy.sh
sudo bash deploy/a1/backup.sh
# Pull the new backup off-instance again.
```

The deploy script backs up an existing DB before migrations, records previous
and attempted SHAs, and marks current only after health checks. Keep the
corresponding archive for every update. Rebuilding uses upstream base tags and
backend dependency ranges, so the exact future image bytes may change; retain
working tagged images locally and use the pinned code plus validation on a new
server. Full dependency/image locking is later hardening.

Docker daemon restart is a valid simulation only when no unrelated containers
will be interrupted. `unless-stopped` recovers running containers after a daemon
restart/reboot; explicitly stopped containers stay stopped. A whole-server reboot
must be separately scheduled when safe. Do not claim a simulated restart was an
actual reboot.

## Consistent backup and off-instance recovery

```sh
cd /opt/gorofan
sudo bash deploy/a1/backup.sh
```

The script uses SQLite's online backup API, verifies integrity and migration
head, and archives DB, media, extra persistent files, and source SHA. It excludes
live DB/WAL/SHM files. It never archives env secrets. SQLite is consistent while
live; media/extra files are copied afterward. For a jointly quiescent media/DB
snapshot, stop this project's frontend/backend around backup, then start them.
An interrupted archive is not a verified backup; only trust successful script
completion and validate archives after transfer.

Instance-local archives are staging, not reclamation protection. Existing OCI,
external backup credentials, or another backup target should be reused if
available. An optional root-owned executable `/etc/gorofan/backup-upload` (700)
receives the verified archive path; implement authenticated external transfer
there, with credentials outside Git. Hook failure fails backup. The upload
success marker is an operational signal, not proof of remote retention/restore.
The managed-PC helper records a separate `last-managed-pc-copy` receipt only
after archive and env SHA-256 verification. `check.sh` reports both receipts and
warns if either is older than 24 hours. Keep checking the PC copy's retention.

When no external hook exists, use the provided Windows managed-PC pull script:

```powershell
.\deploy\a1\backup-to-pc.ps1 -SshTarget <existing-ssh-host> `
  -IdentityFile <existing-key-path> -Destination <private-path-outside-checkout>
```

It makes a new server backup, transfers it as binary without PowerShell text
redirection, and checks the server SHA-256. The destination has inheritance
disabled and permits only the current Windows user. It separately retains the
production env for recovery; the key is never printed. This is a manual
off-instance backup, not a scheduled service. Repeat after meaningful changes
and before updates; configure a real upload hook/schedule if unattended backups
are needed. Put the production secret in your password manager/encrypted backup
too, and protect the managed PC with disk encryption. Never back up secrets to
GitHub. The encrypted provider data requires the SAME APP_SECRET_KEY after
restoration; losing it makes that data undecryptable.

## Restore and rollback

Keep services stopped during a restore. Never overlay a live DB. Verify the
archive SHA-256 against its saved receipt, extract into a separate empty staging
directory, inspect its file list for unsafe paths/links, and check SQLite with
`PRAGMA integrity_check` and `select version_num from alembic_version`.

For a **fresh empty** `/srv/gorofan/data`, copy the staged `app.db` and `media/`
there and extract `extra-data.tar.gz` after inspecting it. Keep ownership root,
directories 700 and files readable only as required. Restore the secret env
separately to `/etc/gorofan/gorofan.env` as root:root 600. Do not restore backup
staging, live WAL/SHM, or a development database as production data.

For an existing deployment, first stop only gorofan, take a backup, and move
its data to a distinct timestamped preservation directory. Never delete it.
Restore into a fresh data directory. Run migration/head verification before
starting. A DB restore discards writes newer than that snapshot; select the
archive deliberately.

Rollback code using `/srv/gorofan/state/previous-commit` and existing tagged
images when available. Record the failed SHA, fetch/synchronize first, preserve
the DB, and verify older code is compatible with the current schema. A manual
rollback can use `GOROFAN_DEPLOY_SHA=<previous-sha>` with `common.sh` and
`compose up -d --no-build --wait backend frontend`; verify health and record
the actual image SHA in state. Restore the matching checkout in a separate
approved rollback operation; `deploy.sh` deliberately refuses detached/stale
checkouts. Do not run `alembic downgrade` automatically. When a schema is
incompatible, restore the matching pre-update data backup while stopped before
launching its matching images/code. Document the recovery point/data loss.

## Fresh A1 disaster recovery drill

1. Obtain a supported Ubuntu A1 and establish SSH; IP may change. Do not create
   another instance as part of an update to the existing deployment.
2. Inventory and preserve existing services; clone `/opt/gorofan`, fetch,
   checkout approved main/operations branch, pull, confirm clean exact SHA.
3. Install Docker using `bootstrap.sh` **without** `--init-secret`. For a full
   recovery, first restore the saved env into root-owned `/etc/gorofan` (700)
   and env file (600), then run bootstrap. Add `--with-swap` on small RAM hosts.
4. Transfer the verified off-instance archive, inspect/extract to staging, and
   restore DB/media/extra data into the empty persistent path as above.
5. Run `deploy.sh`: build ARM64 images, migrate/check head, start services.
6. Run `check.sh`; verify data contents and required provider key decryptability
   without making an unsolicited live provider request.
7. Verify recreation/restart recovery, Docker enabled, and existing services.
8. Point the SSH tunnel at the new server; validate browser/API connectivity.
9. Create and pull a new external backup and retain the same production secret.

This runbook enables recovery; full fresh-instance provisioning is not itself
tested unless explicitly recorded. On an empty-host restore, never generate a
replacement secret before restoring encrypted production data.

## Optional public HTTPS and troubleshooting

Public HTTPS is outside this baseline's completion criteria. Before any public
exposure, verify real OAuth login/auth, exact CORS and redirect origins,
production secrets, TLS, and patched application dependencies. The initial A1
build of current main emitted npm audit warnings (42 findings, including two
critical), and Next 14.2.5's upstream security warning. Do not run audit-fix/major
upgrades opportunistically during deployment; review/test a patched dependency
update before public ingress. See the [Next.js security advisory](https://nextjs.org/blog/security-update-2025-12-11).
Reuse an existing nginx/Caddy proxy; avoid duplicate
proxies. Only then review OS firewall and OCI Security List/NSG rules for 80/443.
Keep 3000/8000 host sockets local and preserve the existing SSH rule.

If health fails: check migration logs and bind mount permissions, then image
state, frontend build-time `/api/v1` and rewrite target, port collisions, free
disk/RAM/swap, and backup freshness. Runtime NEXT_PUBLIC variables do not replace
the browser bundle's build-time settings: rebuild frontend after changing them.
If migration fails, services remain stopped; preserve DB and inspect the failure.
Do not prune volumes or regenerate the secret to fix startup.

## Oracle reclamation

As checked 2026-09-13, Oracle's official policy says idle Always Free instances
may be reclaimed when over 7 days CPU utilization's 95th percentile is <20%,
network utilization is <20%, and (A1 only) memory utilization is <20%.
The current official A1 Always Free allowance is 2 OCPUs / 12 GiB equivalent;
check the console's tenancy/account status, eligibility and usage metrics rather
than assuming a shape alone proves account status or predicts reclamation.

Running this real application does not guarantee avoiding reclamation. Do not
add CPU burn, fake traffic, memory reservation or artificial benchmark cron.
Maintain off-instance data **and** secret backups and rehearse restoration.

Source: [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm#compute__idleinstances).

## Initial actual A1 validation (2026-09-13)

The initial deployment/tested application commit was
`fc1d41974743cdde100235aabef0c714b36059a3`, containing the main baseline above.
After operational script/document refinements, redeploy the final branch head;
the state file and image tags remain the authority for the current running SHA.

| Check | Actual result |
| --- | --- |
| Inventory | Ubuntu 24.04.4 LTS, AArch64, OCI A1 shape, metadata 1 OCPU / 1 GiB RAM |
| Disk | 45 GiB root filesystem, about 38 GiB free after build |
| Docker / Compose | 29.1.3 / 2.40.3 (Ubuntu packages); Docker enabled |
| Existing service | `vr-monitor` at localhost:8010 preserved; same PID after Docker restart |
| Images | Python and Node ARM64 manifests verified; both images built on A1 |
| Backend | Running/healthy; `/healthz` HTTP 200 |
| Frontend | Running/healthy; `/` and proxied `/api/v1/auth/me` HTTP 200 |
| Browser | Managed-PC SSH tunnel: home renders, proposal/chat/novel lists load |
| SQLite | Fresh DB, exact `0003_edit_diff_capture`, persistent host mount |
| Recreation | Both containers recreated; same DB inode, user rows and schema retained |
| Restart | Docker daemon restarted; both healthy without running compose up |
| Whole-server reboot | Not performed; daemon restart simulation only |
| Secret/logs | Random external key, root:root 600; key absent from captured app logs |
| Backup | SQLite online backup integrity/head verified; DB/media archive generated |
| Off-instance | Archive and separate env pulled to private managed-PC directory; SHA-256 verified |
| Restore validation | PC archive extracted; SQLite integrity/head and user rows verified |
| Full new A1 drill | Runbook provided; no new instance provisioned/tested |
| Resource sample after restart | About 413 MiB RAM used, 534 MiB available; app containers about 69/35 MiB |
| Build resource safety | Sequential builds, one Next worker, 2 GiB swap; no OOM observed |
| Public/auth/TLS | No public gorofan ingress; AUTH disabled, SSH-only; TLS/auth hardening pending |
| OCI rules/account | No OCI credentials/config found; console NSG/Security List and account status unverified |
| Gemini | No credential installed and no live Google generation requested |

Off-instance copies are manual managed-PC backups. Automatic server upload is
not configured; maintain freshness/PC retention or connect the external hook.
This is not a reclamation-prevention guarantee.
