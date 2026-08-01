#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
PYTHON="$RUNTIME_DIR/.venv/bin/python"
ARCHIVE="/root/meta-ads-phase5-final.tar.gz"
STAMP="$(date +%Y%m%d-%H%M%S)"

active_sessions="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from browser_sessions where status in ('starting','active','closing');")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','running');")"
chromium_processes="$(pgrep -c chromium || true)"
printf 'active_sessions=%s\nactive_jobs=%s\nchromium_processes=%s\n' \
  "$active_sessions" "$active_jobs" "$chromium_processes"
if [[ "$active_sessions" != "0" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing final deployment while browser work is active.\n' >&2
  exit 20
fi

tar -tzf "$ARCHIVE" >/dev/null
tar -xzf "$ARCHIVE" -C "$APP_DIR"

cd "$APP_DIR"
"$PYTHON" -W error::SyntaxWarning -m compileall -q backend workers
if "$PYTHON" -c "import pytest" 2>/dev/null; then
  "$PYTHON" -m pytest -q
else
  printf 'pytest=skipped (production runtime has no dev dependency)\n'
fi
set -a
source /etc/meta-ads-copilot/app.env
set +a
"$RUNTIME_DIR/.venv/bin/alembic" current
"$RUNTIME_DIR/.venv/bin/alembic" check

systemctl restart meta-ads-copilot-web.service
for _ in {1..20}; do
  if curl -fsS http://172.17.0.1:8021/login >/dev/null; then
    break
  fi
  sleep 0.5
done
systemctl restart meta-ads-copilot-worker.service
systemctl is-active --quiet meta-ads-copilot-web.service
systemctl is-active --quiet meta-ads-copilot-worker.service

public_status="$(curl -sS -o /dev/null -w '%{http_code}' https://ads.lushmedia.net/)"
printf 'public_status=%s\n' "$public_status"
if [[ "$public_status" != "200" && "$public_status" != "303" ]]; then
  exit 21
fi

final_dump="$RUNTIME_DIR/postgres-backups/meta-ads-phase5-final-$STAMP.dump"
docker exec meta-ads-postgres pg_dump -U meta_ads_owner -d meta_ads_copilot -Fc > "$final_dump"
docker exec -i meta-ads-postgres pg_restore -l < "$final_dump" >/dev/null
printf 'final_dump=%s\n' "$final_dump"
stat -c '%n %s bytes' "$final_dump"
