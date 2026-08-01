#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
PYTHON="$RUNTIME_DIR/.venv/bin/python"
ARCHIVE="/root/meta-ads-phase8-final.tar.gz"
STAMP="$(date +%Y%m%d-%H%M%S)"

active_sessions="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from browser_sessions where status in ('requested','starting','awaiting_user','ready','closing');")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','claimed','running');")"
chromium_processes="$(pgrep -c chromium || true)"
printf 'active_sessions=%s\nactive_jobs=%s\nchromium_processes=%s\n' \
  "$active_sessions" "$active_jobs" "$chromium_processes"
if [[ "$active_sessions" != "0" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing Phase 8 deployment while browser work is active.\n' >&2
  exit 20
fi

tar -tzf "$ARCHIVE" >/dev/null
tar -xzf "$ARCHIVE" -C "$APP_DIR"
cd "$APP_DIR"
"$PYTHON" -W error::SyntaxWarning -m compileall -q backend workers scripts tests migrations
node --check backend/app/static/campaigns.js
node --check backend/app/static/workspace.js
node --check backend/app/static/reports.js

set -a
# shellcheck disable=SC1091
source /etc/meta-ads-copilot/app.env
set +a
"$RUNTIME_DIR/.venv/bin/alembic" upgrade head
"$RUNTIME_DIR/.venv/bin/alembic" current
"$RUNTIME_DIR/.venv/bin/alembic" check

systemctl restart meta-ads-copilot-web.service
for _ in {1..30}; do
  if curl -fsS http://172.17.0.1:8021/health >/dev/null; then
    break
  fi
  sleep 0.5
done
curl -fsS http://172.17.0.1:8021/health
systemctl restart meta-ads-copilot-worker.service
systemctl is-active --quiet meta-ads-copilot-web.service
systemctl is-active --quiet meta-ads-copilot-worker.service

schema_state="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from information_schema.tables where table_schema='public' and table_name in ('report_schedules','report_jobs','report_snapshots');")"
printf '\nreporting_tables=%s\n' "$schema_state"
[[ "$schema_state" == "3" ]]

public_status="$(curl -sS -o /dev/null -w '%{http_code}' https://ads.lushmedia.net/reports)"
printf 'public_reports_status=%s\n' "$public_status"
if [[ "$public_status" != "200" && "$public_status" != "303" ]]; then
  exit 21
fi

if journalctl -u meta-ads-copilot-web.service -u meta-ads-copilot-worker.service \
  --since '-2 minutes' --no-pager | grep -E 'Traceback|SyntaxError|ModuleNotFoundError'; then
  printf 'Runtime error found after restart.\n' >&2
  exit 22
fi

final_dump="$RUNTIME_DIR/postgres-backups/meta-ads-phase8-final-$STAMP.dump"
docker exec meta-ads-postgres pg_dump -U meta_ads_owner -d meta_ads_copilot -Fc > "$final_dump"
docker exec -i meta-ads-postgres pg_restore -l < "$final_dump" >/dev/null
printf 'final_dump=%s\n' "$final_dump"
stat -c '%n %s bytes' "$final_dump"

