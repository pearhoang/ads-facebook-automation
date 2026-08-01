#!/usr/bin/env bash
set -euo pipefail

WEB_SERVICE="meta-ads-copilot-web.service"
WORKER_SERVICE="meta-ads-copilot-worker.service"
APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
STAMP="$(date +%Y%m%d-%H%M%S)"

systemctl is-active --quiet "$WEB_SERVICE"
systemctl is-active --quiet "$WORKER_SERVICE"

active_sessions="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from browser_sessions where status in ('starting','active','closing');")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','running');")"
chromium_processes="$(pgrep -c chromium || true)"

printf 'active_sessions=%s\n' "$active_sessions"
printf 'active_jobs=%s\n' "$active_jobs"
printf 'chromium_processes=%s\n' "$chromium_processes"

if [[ "$active_sessions" != "0" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing deployment backup while browser work is active.\n' >&2
  exit 20
fi

mkdir -p "$RUNTIME_DIR/postgres-backups" "$RUNTIME_DIR/source-backups"
db_backup="$RUNTIME_DIR/postgres-backups/meta-ads-phase5-predeploy-$STAMP.dump"
source_backup="$RUNTIME_DIR/source-backups/meta-ads-phase5-predeploy-$STAMP.tar.gz"

docker exec meta-ads-postgres pg_dump -U meta_ads_owner -d meta_ads_copilot -Fc > "$db_backup"
tar -czf "$source_backup" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"

docker exec -i meta-ads-postgres pg_restore -l < "$db_backup" >/dev/null
tar -tzf "$source_backup" >/dev/null

printf 'db_backup=%s\n' "$db_backup"
printf 'source_backup=%s\n' "$source_backup"
stat -c '%n %s bytes' "$db_backup" "$source_backup"
