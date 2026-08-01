#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
PROFILE_ROOT="$RUNTIME_DIR/worker-data/browser-profiles"
SHARED_PROFILE="/root/snap/chromium/common/chromium"
OLD_PROFILE_KEY="2d67ab0a-ac12-45b0-b2b4-410c16b1202f"
NEW_PROFILE_KEY="d8824f1a-994c-425a-b49e-91a85a21a553"
WRONG_SESSION_ID="06cc1160-4aaa-4974-b54a-e47ac1ac51b9"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$RUNTIME_DIR/profile-isolation-backups/$STAMP"

session_status="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select status from browser_sessions where id='$WRONG_SESSION_ID';")"
active_jobs="$(docker exec meta-ads-postgres psql -U meta_ads_owner -d meta_ads_copilot -Atc \
  "select count(*) from execution_jobs where status in ('queued','running');")"
chromium_processes="$(pgrep -c chromium || true)"
printf 'wrong_session_status=%s\nactive_jobs=%s\nchromium_processes=%s\n' \
  "$session_status" "$active_jobs" "$chromium_processes"
if [[ "$session_status" != "closed" || "$active_jobs" != "0" || "$chromium_processes" != "0" ]]; then
  printf 'Refusing profile migration while browser work is active.\n' >&2
  exit 20
fi

for path in "$PROFILE_ROOT/$OLD_PROFILE_KEY" "$PROFILE_ROOT/$NEW_PROFILE_KEY" "$SHARED_PROFILE"; do
  [[ -d "$path" ]] || { printf 'Missing required profile path: %s\n' "$path" >&2; exit 21; }
done

mkdir -p "$BACKUP_DIR"
docker exec meta-ads-postgres pg_dump -U meta_ads_owner -d meta_ads_copilot -Fc \
  > "$BACKUP_DIR/meta-ads-before-profile-isolation.dump"
tar -czf "$BACKUP_DIR/source-before-profile-isolation.tar.gz" -C /opt meta-ads-copilot
tar -czf "$BACKUP_DIR/shared-snap-profile.tar.gz" -C "$(dirname "$SHARED_PROFILE")" "$(basename "$SHARED_PROFILE")"
tar -czf "$BACKUP_DIR/account-profiles-before.tar.gz" -C "$PROFILE_ROOT" "$OLD_PROFILE_KEY" "$NEW_PROFILE_KEY"
install -m 0600 /etc/meta-ads-copilot/app.env "$BACKUP_DIR/app.env"
install -m 0600 /etc/meta-ads-copilot/worker.env "$BACKUP_DIR/worker.env"

docker exec -i meta-ads-postgres pg_restore -l \
  < "$BACKUP_DIR/meta-ads-before-profile-isolation.dump" >/dev/null
for archive in "$BACKUP_DIR"/*.tar.gz; do tar -tzf "$archive" >/dev/null; done

# Historical sessions used the snap-global directory. Preserve it untouched and
# seed only the original test account profile with that state.
cp -a "$SHARED_PROFILE/." "$PROFILE_ROOT/$OLD_PROFILE_KEY/"

[[ -f "$PROFILE_ROOT/$OLD_PROFILE_KEY/Default/Cookies" ]]
if [[ -f "$PROFILE_ROOT/$NEW_PROFILE_KEY/Default/Cookies" ]]; then
  printf 'New account profile unexpectedly contains Cookies before isolated launch.\n' >&2
  exit 22
fi

printf 'backup_dir=%s\n' "$BACKUP_DIR"
printf 'shared_cookie_sha256='; sha256sum "$SHARED_PROFILE/Default/Cookies" | awk '{print $1}'
printf 'old_cookie_sha256='; sha256sum "$PROFILE_ROOT/$OLD_PROFILE_KEY/Default/Cookies" | awk '{print $1}'
du -sh "$BACKUP_DIR" "$PROFILE_ROOT/$OLD_PROFILE_KEY" "$PROFILE_ROOT/$NEW_PROFILE_KEY"
