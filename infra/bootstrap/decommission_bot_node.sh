#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
APP_DIR="/opt/meta-ads-copilot"
PURGE_DATA=false
FORCE=false
for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE_DATA=true ;;
    --force) FORCE=true ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

STATE_DB="$RUNTIME_DIR/worker-data/worker-state.sqlite3"
if [[ -f "$STATE_DB" && "$FORCE" != true ]]; then
  ACTIVE="$(sqlite3 "$STATE_DB" "SELECT COUNT(*) FROM assignments WHERE local_status IN ('claimed','running');" 2>/dev/null || echo 1)"
  OUTBOX="$(sqlite3 "$STATE_DB" "SELECT COUNT(*) FROM outbox;" 2>/dev/null || echo 1)"
  if [[ "$ACTIVE" != "0" || "$OUTBOX" != "0" ]]; then
    echo "Refusing decommission: active assignments=$ACTIVE, outbox=$OUTBOX. Drain/sync first or use --force." >&2
    exit 1
  fi
fi

systemctl disable --now meta-ads-copilot-hermes.service meta-ads-copilot-worker.service || true
rm -f /etc/systemd/system/meta-ads-copilot-hermes.service /etc/systemd/system/meta-ads-copilot-worker.service
systemctl daemon-reload

if [[ "$PURGE_DATA" == true ]]; then
  echo "Purge requested for $RUNTIME_DIR and $APP_DIR. Run after verifying backups."
  exit 3
fi
echo "Services removed. Source and browser profiles were preserved for recovery."
