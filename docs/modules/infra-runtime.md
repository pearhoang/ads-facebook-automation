# Infra Runtime

## Responsibility

- Host thử nghiệm: `82.197.71.6`, Ubuntu 24.04.
- App: `/opt/meta-ads-copilot`.
- Persistent runtime: `/opt/meta-ads-copilot-runtime`.
- Secrets/env: `/etc/meta-ads-copilot`.
- Web/worker chạy bằng systemd; Caddy dùng chung chạy trong Docker.
- PostgreSQL chạy trong dedicated container `meta-ads-postgres`.

## Network Boundaries

- Uvicorn bind `172.17.0.1:8021`; không public trên `eth0`.
- Caddy container proxy qua `host.docker.internal:8021`.
- x11vnc và websockify bind localhost; browser UI đi qua FastAPI proxy.
- CDP chỉ bind mặc định trên host runtime và không được expose qua reverse proxy.
- PostgreSQL chỉ bind `127.0.0.1:55432`.
- Hermes native dashboard bind Docker host interface `172.17.0.1:9119`, yêu cầu Hermes basic auth và chỉ được Caddy proxy; không listen trên public interface. Caddy rewrite riêng WebSocket `Host` và `Origin` về private bind để vượt qua DNS-rebinding guard chính chủ của Hermes.

## Domain

- Canonical URL: `https://ads.lushmedia.net` dùng application authentication.
- Hermes URL: `https://hermes.ads.lushmedia.net` dùng dashboard authentication chính chủ của Hermes.
- Cloudflare record `A ads -> 82.197.71.6` đã hoạt động.
- Cloudflare record `A hermes.ads -> 82.197.71.6` đã hoạt động ở chế độ DNS only.
- Caddy đã cấp chứng chỉ Let's Encrypt cho `ads.lushmedia.net`; IP HTTP redirect sang domain này.
- Caddy đã cấp chứng chỉ Let's Encrypt cho `hermes.ads.lushmedia.net`; certificate hiện tại hết hạn ngày 2026-10-30.

## Current Deployment

- Deployed: 2026-07-31.
- Web và worker đang `active`.
- Caddy Basic Auth đã được gỡ; app redirect user chưa đăng nhập tới `/login`.
- IP HTTP redirect vĩnh viễn sang domain HTTPS; production OpenAPI docs bị tắt.
- Caddy backup trước thay đổi: `/opt/spoticheck/app/deploy/Caddyfile.backup-meta-ads-20260731-1830`.
- Worker dùng `BROWSER_SESSION_PUBLIC_BASE_URL=https://ads.lushmedia.net`.
- Web dùng PostgreSQL 17.10; Alembic revision `20260801_0006` đang ở `head`.
- Phase 4 Meta draft builder đã deploy tại `/campaigns`; có browser mutation cho unpublished draft nhưng chưa có Meta publish executor.
- Production smoke đã tạo sạch một draft Sales gồm campaign/ad set/ad, lưu 4 checkpoint và dừng `awaiting_user` ở bước Ad do thiếu Page/creative/URL.
- Phase 4 backup trước deploy: `/opt/meta-ads-copilot-runtime/backups/source-before-phase4-20260731-154448.tar.gz` và `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-before-phase4-20260731-154448.dump`.
- Phase 4 final verified dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase4-final-20260731-160702.dump`.
- Phase 5 objective adapters đã deploy; UI/API production smoke đủ sáu objective và không tạo campaign test.
- Phase 5 predeploy backups: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase5-predeploy-20260731-165931.dump` và `/opt/meta-ads-copilot-runtime/source-backups/meta-ads-phase5-predeploy-20260731-165931.tar.gz`.
- Phase 5 final verified dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase5-final-20260731-170626.dump`.
- Phase 6 deterministic field filling đã deploy; public objective API trả sáu adapter `field_filling`, web/worker active và UI console sạch.
- Phase 6 predeploy backups: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase6-predeploy-20260731-172437.dump` và `/opt/meta-ads-copilot-runtime/source-backups/meta-ads-phase6-predeploy-20260731-172437.tar.gz`.
- Phase 6 final verified dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase6-final-20260731-173605.dump`.
- Phase 7 resource/asset registry và human handoff đã deploy; Alembic revision `20260731_0004` ở `head`.
- Phase 7 predeploy backups: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase7-predeploy-20260731-180430.dump`, `/opt/meta-ads-copilot-runtime/source-backups/meta-ads-phase7-predeploy-20260731-180430.tar.gz` và env backup trong `backups/app.env-before-phase7-20260731-180430`.
- Phase 7 final verified dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase7-final-20260731-180501.dump`; creative asset root là `/opt/meta-ads-copilot-runtime/creative-assets`.
- Phase 6 discovery smoke `6982633575177` đã cleanup exact ID/name với `published=false`; legitimate campaign `6982618414377` được giữ nguyên.
- Execution artifacts lưu tại `/opt/meta-ads-copilot-runtime/execution-artifacts`.
- Creative assets lưu tại `/opt/meta-ads-copilot-runtime/creative-assets`, không nằm trong source deploy.
- Worker dùng direct Snap Chromium binary `/snap/chromium/current/usr/lib/chromium-browser/chrome`; không dùng snap launcher cho account session.
- Profile isolation backup: `/opt/meta-ads-copilot-runtime/profile-isolation-backups/20260731-182436`; chứa PG/source/env, shared Snap profile và hai account profile trước migration.
- PostgreSQL data ở `/opt/meta-ads-copilot-runtime/postgres-data`; dump ở `postgres-backups`.
- Real browser smoke test đã launch/close sạch và nhận `RFB 003.008` qua `wss://ads.lushmedia.net`.
- Phase 8 reporting/KPI đã deploy; Alembic `20260801_0005` ở `head`, `/reports` hoạt động và production smoke tạo snapshot read-only thành công.
- Phase 8 predeploy backup: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase8-predeploy-20260801-113209.dump`, `/opt/meta-ads-copilot-runtime/source-backups/meta-ads-phase8-predeploy-20260801-113209.tar.gz` và worker env backup tương ứng.
- Phase 8 post-smoke verified dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase8-post-smoke-20260801-113531.dump`.
- `TELEGRAM_BOT_TOKEN` đã cấu hình trên production worker và report Telegram đã được user xác nhận nhận thành công; token không nằm trong source/database.
- Multi-VPS fleet/AI settings đã deploy; worker hiện hữu có host `82.197.71.6`, Hermes Agent `v0.19.1` đã cài nhưng service chỉ được enable/start sau khi có provider config.
- Phase 8 fleet predeploy backup: `/opt/meta-ads-backups/20260801-125156`.
- Production source đã chuyển thành Git checkout sạch tracking `pearhoang/ads-facebook-automation` branch `main`; `WORKER_BOOTSTRAP_REPO_URL` trỏ cùng repo.
- Backup trước chuyển Git checkout: `/opt/meta-ads-backups/20260801-132105-git-checkout`.
- Auth source/database/app env backup: `/opt/meta-ads-copilot-runtime/backups/*-before-auth-20260731-184227*`.
- Caddy auth migration backup: `/opt/spoticheck/app/deploy/Caddyfile.backup-auth-20260731-184555`.
- Native Hermes Dashboard đã deploy từ commit `3164426`; login basic auth, session Telegram, Chat PTY và tool event feed đều được smoke test qua public HTTPS. Smoke session `20260801_193914_2fc1bf` đã xóa sau kiểm thử.
- Native dashboard backup: `/var/backups/meta-ads-copilot/20260801T171727Z-native-hermes-dashboard`; Caddy WebSocket fix backup: `/opt/spoticheck/app/deploy/Caddyfile.pre-hermes-ws-20260801T173809Z`.

## Services

- `meta-ads-copilot-web.service`
- `meta-ads-copilot-worker.service`
- `meta-ads-copilot-hermes.service` (gateway; active khi worker đã có AI provider config)
- `meta-ads-copilot-hermes-dashboard.service` (chỉ start khi có config, dashboard env và built SPA)
- `meta-ads-postgres` Docker container

## Safety

- Backup Caddyfile trước mỗi thay đổi.
- Validate bằng `caddy validate` trong container trước khi reload.
- Không restart container/app không liên quan.
- Không xóa browser profile khi đóng session.

## Operations

- Status: `systemctl status meta-ads-copilot-web.service meta-ads-copilot-worker.service`
- Logs: `journalctl -u meta-ads-copilot-web.service -u meta-ads-copilot-worker.service -f`
- Health: `curl http://172.17.0.1:8021/health`
- Source: `/opt/meta-ads-copilot`
- Git update: `git -C /opt/meta-ads-copilot pull --ff-only origin main`
- Persistent data: `/opt/meta-ads-copilot-runtime`
- Secrets: `/etc/meta-ads-copilot` mode `0600`; không copy vào repo.
- Database status: `docker inspect -f '{{.State.Status}} {{.State.Health.Status}}' meta-ads-postgres`
- Migration: `cd /opt/meta-ads-copilot && /opt/meta-ads-copilot-runtime/.venv/bin/alembic upgrade head`
