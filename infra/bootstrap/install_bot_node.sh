#!/usr/bin/env bash
set -euo pipefail

CONTROL_PLANE=""
ENROLLMENT_TOKEN=""
REPO_URL=""
REPO_BRANCH="main"
APP_DIR="/opt/meta-ads-copilot"
RUNTIME_DIR="/opt/meta-ads-copilot-runtime"
ENV_DIR="/etc/meta-ads-copilot"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --control-plane) CONTROL_PLANE="$2"; shift 2 ;;
    --token) ENROLLMENT_TOKEN="$2"; shift 2 ;;
    --repo) REPO_URL="$2"; shift 2 ;;
    --branch) REPO_BRANCH="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    --runtime-dir) RUNTIME_DIR="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$CONTROL_PLANE" || -z "$ENROLLMENT_TOKEN" || -z "$REPO_URL" ]]; then
  echo "Required: --control-plane --token --repo" >&2
  exit 2
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this installer with sudo/root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq xz-utils python3 python3-venv python3-pip \
  xvfb openbox x11vnc novnc websockify ffmpeg snapd sqlite3

if ! command -v chromium >/dev/null 2>&1 && [[ ! -x /snap/chromium/current/usr/lib/chromium-browser/chrome ]]; then
  snap install chromium
fi

mkdir -p "$RUNTIME_DIR" "$ENV_DIR"
chmod 700 "$ENV_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --prune origin "$REPO_BRANCH"
  git -C "$APP_DIR" checkout "$REPO_BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$REPO_BRANCH"
elif [[ -e "$APP_DIR" ]]; then
  echo "$APP_DIR exists but is not a Git checkout; refusing to overwrite." >&2
  exit 1
else
  git clone --branch "$REPO_BRANCH" --single-branch "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$RUNTIME_DIR/.venv"
"$RUNTIME_DIR/.venv/bin/python" -m pip install --upgrade pip wheel
"$RUNTIME_DIR/.venv/bin/python" -m pip install -e "$APP_DIR"

ENROLL_RESPONSE="$(mktemp)"
trap 'rm -f "$ENROLL_RESPONSE" /tmp/hermes-agent-install.sh' EXIT
curl -fsS "$CONTROL_PLANE/api/bot-nodes/enroll" \
  -H 'Content-Type: application/json' \
  --data "$(jq -cn --arg token "$ENROLLMENT_TOKEN" '{enrollment_token:$token,runtime_version:"0.2.0",agent_version:"managed",capabilities:{browser:true,novnc:true,execution:true,hermes:true,durable_outbox:true}}')" \
  > "$ENROLL_RESPONSE"

WORKER_ID="$(jq -er '.worker.id' "$ENROLL_RESPONSE")"
WORKER_KEY="$(jq -er '.worker.worker_key' "$ENROLL_RESPONSE")"
WORKER_NAME="$(jq -er '.worker.display_name' "$ENROLL_RESPONSE")"
WORKER_CREDENTIAL="$(jq -er '.worker_credential' "$ENROLL_RESPONSE")"
WORKER_DATA_DIR="$RUNTIME_DIR/worker-data"
mkdir -p "$WORKER_DATA_DIR/hermes"
printf '%s' "$WORKER_CREDENTIAL" > "$WORKER_DATA_DIR/worker.credential"
chmod 600 "$WORKER_DATA_DIR/worker.credential"

cat > "$ENV_DIR/worker.env" <<EOF
CONTROL_PLANE_URL=$CONTROL_PLANE
WORKER_CREDENTIAL_FILE=$WORKER_DATA_DIR/worker.credential
WORKER_KEY=$WORKER_KEY
WORKER_NAME=$WORKER_NAME
WORKER_DATA_DIR=$WORKER_DATA_DIR
WORKER_RUNTIME_VERSION=0.2.0
HERMES_AGENT_VERSION=managed
HERMES_HOME=$WORKER_DATA_DIR/hermes
WORKER_POLL_SECONDS=3
WORKER_HEARTBEAT_SECONDS=15
BROWSER_SESSION_ENABLED=true
BROWSER_SESSION_PUBLIC_BASE_URL=$CONTROL_PLANE
BROWSER_SESSION_START_URL=https://business.facebook.com/adsmanager/manage/campaigns
BROWSER_SESSION_BIND_HOST=127.0.0.1
BROWSER_SESSION_CHROMIUM_BIN=/snap/chromium/current/usr/lib/chromium-browser/chrome
BROWSER_SESSION_SNAP_DIRECT_BIN=/snap/chromium/current/usr/lib/chromium-browser/chrome
BROWSER_SESSION_NOVNC_WEB_DIR=/usr/share/novnc
BROWSER_SESSION_PROFILE_ROOT=$WORKER_DATA_DIR/browser-profiles
BROWSER_SESSION_STATE_ROOT=$WORKER_DATA_DIR/browser-sessions
BROWSER_SESSION_DISPLAY_BASE=190
BROWSER_SESSION_VNC_PORT_BASE=15900
BROWSER_SESSION_WEB_PORT_BASE=16080
BROWSER_SESSION_DEBUG_PORT_BASE=19220
BROWSER_SESSION_SLOT_COUNT=10
BROWSER_SESSION_VIEWPORT=1440,900
EXECUTION_PREFLIGHT_ENABLED=true
EXECUTION_PREFLIGHT_DEBUG_PORT=19350
EXECUTION_PREFLIGHT_TIMEOUT_SECONDS=45
TELEGRAM_BOT_TOKEN=
EOF
chmod 600 "$ENV_DIR/worker.env"

curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-agent-install.sh
bash /tmp/hermes-agent-install.sh --skip-setup --skip-browser --hermes-home "$WORKER_DATA_DIR/hermes"

install -m 0644 "$APP_DIR/infra/systemd/meta-ads-copilot-worker.service" /etc/systemd/system/meta-ads-copilot-worker.service
install -m 0644 "$APP_DIR/infra/systemd/meta-ads-copilot-hermes.service" /etc/systemd/system/meta-ads-copilot-hermes.service
systemctl daemon-reload
systemctl enable --now meta-ads-copilot-worker.service

echo "Bot VPS enrolled: $WORKER_NAME ($WORKER_KEY / $WORKER_ID)"
systemctl --no-pager --full status meta-ads-copilot-worker.service || true
