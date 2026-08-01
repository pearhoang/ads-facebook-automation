#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
OUTPUT_DIR="$RUNTIME_DIR/phase6-field-inspection-$(date +%Y%m%d-%H%M%S)"
WORKER_SERVICE="meta-ads-copilot-worker.service"

active_sessions="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from browser_sessions where status in ('starting','active','closing');")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','running');")"
chromium_processes="$(pgrep -c chromium || true)"
printf 'active_sessions=%s\nactive_jobs=%s\nchromium_processes=%s\n' \
  "$active_sessions" "$active_jobs" "$chromium_processes"
if [[ "$active_sessions" != "0" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing read-only inspection while browser work is active.\n' >&2
  exit 20
fi

restart_worker() {
  systemctl start "$WORKER_SERVICE"
}
trap restart_worker EXIT
systemctl stop "$WORKER_SERVICE"

while IFS='=' read -r key value; do
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
  export "$key=$value"
done < /etc/meta-ads-copilot/worker.env
cd "$APP_DIR"
"$RUNTIME_DIR/.venv/bin/python" scripts/inspect_meta_draft_fields.py \
  --confirmation "INSPECT META DRAFT FIELDS READ ONLY" \
  --profile-key "2d67ab0a-ac12-45b0-b2b4-410c16b1202f" \
  --ad-account-id "1018982660898479" \
  --campaign-id "6982618414377" \
  --adset-id "6982618414777" \
  --ad-id "6982618414577" \
  --output-dir "$OUTPUT_DIR"

if pgrep -c chromium >/dev/null; then
  printf 'Chromium remained after inspection.\n' >&2
  exit 21
fi
printf 'output_dir=%s\n' "$OUTPUT_DIR"
