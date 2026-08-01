#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/meta-ads-copilot"
ARCHIVE="/root/meta-ads-profile-isolation-final.tar.gz"
WORKER_ENV="/etc/meta-ads-copilot/worker.env"
DIRECT_BIN="/snap/chromium/current/usr/lib/chromium-browser/chrome"

active_sessions="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from browser_sessions where status in ('requested','starting','awaiting_user','ready','closing');")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','running');")"
chromium_processes="$(pgrep -c chromium || true)"
printf 'active_sessions=%s\nactive_jobs=%s\nchromium_processes=%s\n' \
  "$active_sessions" "$active_jobs" "$chromium_processes"
if [[ "$active_sessions" != "0" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing worker deployment while browser work is active.\n' >&2
  exit 20
fi
[[ -x "$DIRECT_BIN" ]]

tar -tzf "$ARCHIVE" >/dev/null
tar -xzf "$ARCHIVE" -C "$APP_DIR"

set_worker_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$WORKER_ENV"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$WORKER_ENV"
  else
    printf '%s=%s\n' "$key" "$value" >> "$WORKER_ENV"
  fi
}
set_worker_env BROWSER_SESSION_CHROMIUM_BIN "$DIRECT_BIN"
set_worker_env BROWSER_SESSION_SNAP_DIRECT_BIN "$DIRECT_BIN"
chmod 0600 "$WORKER_ENV"

cd "$APP_DIR"
/opt/meta-ads-copilot-runtime/.venv/bin/python -W error::SyntaxWarning -m compileall -q workers tests
systemctl restart meta-ads-copilot-worker.service
systemctl is-active --quiet meta-ads-copilot-worker.service
curl -fsS http://172.17.0.1:8021/health
printf '\nworker=active\ndirect_bin=%s\n' "$DIRECT_BIN"

if journalctl -u meta-ads-copilot-worker.service --since '-2 minutes' --no-pager \
  | grep -E 'Traceback|SyntaxError|ModuleNotFoundError'; then
  printf 'Worker runtime error found after restart.\n' >&2
  exit 22
fi
