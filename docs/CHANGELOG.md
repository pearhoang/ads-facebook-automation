### 2026-07-31 - Bootstrap kiến trúc dự án

- Changed: Tạo project memory, decision ledger và phase đầu Account Session.
- Affected: `AGENTS.md`, `docs/**`.
- Risk: Chưa có runtime code; command build/test sẽ được chốt khi scaffold.

### 2026-07-31 - Scaffold Account Session contract

- Changed: Thêm FastAPI/SQLAlchemy scaffold, worker API, account/session state machine và contract tests.
- Affected: `backend/**`, `workers/**`, `tests/**`, `pyproject.toml`.
- Risk: Chưa có production auth, real noVNC runtime hoặc database migration tooling.

### 2026-07-31 - Deploy Account Session MVP

- Changed: Thêm outbound worker, real Chromium/noVNC runtime, backend WebSocket proxy, Account UI và systemd/Caddy deployment.
- Affected: `backend/**`, `workers/**`, `infra/**`, VPS `82.197.71.6`.
- Verified: `3 passed`, UTF-8/UI check, public Basic Auth, VNC handshake và UI open/close flow.
- Risk: Domain DNS chưa tạo; test auth đang dùng Caddy Basic Auth và SQLite.

### 2026-07-31 - Kích hoạt domain HTTPS

- Changed: Kích hoạt `https://ads.lushmedia.net` và đổi worker public base URL sang domain chuẩn.
- Affected: `infra/worker.env.example`, tài liệu runtime, Caddy và worker env trên VPS.
- Verified: HTTPS health `200`, chứng chỉ Let's Encrypt hợp lệ, noVNC HTML tải thành công, WebSocket nhận `RFB 003.008`, phiên test đóng sạch.
- Risk: Basic Auth và SQLite vẫn chỉ phù hợp cho giai đoạn test.

### 2026-07-31 - Production user/session/tenant auth

- Changed: Thêm Argon2 password, opaque server-side session, tenant membership, CSRF, login/logout UI và owner provisioning CLI; gỡ Caddy Basic Auth.
- Affected: `backend/app/{api,services,templates,static}`, auth models/config, tests, Caddy và production app env.
- Verified: `4 passed`, production login/session/logout, tenant API, noVNC HTML, WebSocket `RFB 003.008`, clean close và IP-to-HTTPS redirect.
- Risk: SQLite/create_all và thiếu reset/invite UI; cần Alembic + PostgreSQL trước dữ liệu production.

### 2026-07-31 - PostgreSQL 17 + Alembic cutover

- Changed: Thêm Alembic baseline, transactional SQLite copy tool và dedicated PostgreSQL 17.10 runtime; production app ngừng `create_all`.
- Affected: `migrations/**`, `scripts/migrate_sqlite_to_postgres.py`, database startup, infra PostgreSQL và VPS app env.
- Verified: `6 passed`, `alembic current/check`, preserved row counts, auth/tenant/account smoke, noVNC/WSS `RFB 003.008`, clean close và verified `pg_dump`.
- Rollback: Giữ SQLite/env/source snapshots trước cutover và PostgreSQL custom-format dump.

### 2026-07-31 - Phase 02 campaign approval foundation

- Changed: Thêm tenant-scoped ad accounts, campaign drafts, immutable approval snapshots, owner/admin approve/reject, audit log và workspace `/campaigns`; không có Meta publish side effect.
- Affected: `backend/app/{models,schemas,api,services,templates,static}`, migration `20260731_0002`, tests và project memory.
- Verified: `9 passed`, compile/JS syntax/UTF-8 scan, Alembic drift sạch, production APIs/page `200`, PostgreSQL/web/worker healthy và `0` active browser session.
- Rollback: Source/env/PG dump trước Phase 2 và final post-deploy dump được giữ trong `/opt/meta-ads-copilot-runtime`.

### 2026-07-31 - Phase 03 execution preflight

- Changed: Thêm execution preview/job queue/lease, explicit `CHẠY PREFLIGHT`, worker headless Chromium/CDP read-only, screenshot artifact và job history/result UI.
- Affected: execution models/service/API, worker runtime/control-plane contract, migration `20260731_0003`, campaign UI, tests và project memory.
- Verified: `13 passed`, compile/JS/UTF-8, Alembic drift sạch, production page/jobs API `200`, worker execution poll `200`, unapproved draft guard `409` và không tạo job giả.
- Safety: Payload bắt buộc `allow_click=false`, `allow_publish=false`; production còn `0` execution job và `0` active browser session sau smoke.
- Rollback: Giữ source/app env/worker env/PG dump trước Phase 3 và final post-deploy dump trong runtime backup paths.

### 2026-07-31 - Phase 04 Meta draft builder

- Changed: Thêm draft-build preview/job, structured Page/targeting/creative spec, deterministic Campaign/Ad Set/Ad state machine, resume-safe retry và checkpoint artifacts.
- Affected: execution backend/API, worker runtime/control-plane, campaign UI, tests và project memory.
- Verified: `15 passed`, compile/JS/UTF-8/Alembic drift sạch; production tạo mới 3 unpublished Meta entities và dừng `awaiting_user` ở bước Ad do thiếu Page/primary text/URL.
- Safety: Draft cũ đã xóa có exact-name guard; job mới giữ `allow_publish=false`, lưu `safety.published=false` và không click nút `Đăng`.

### 2026-07-31 - Phase 05 objective adapters

- Changed: Khảo sát sáu objective Meta, thêm canonical adapter/API, conditional campaign form, objective-specific preview và Traffic manual setup; retry chỉ resume exact campaign name.
- Affected: campaign backend/UI, execution payload, worker state machine, discovery scripts, tests và project memory.
- Verified: `19 passed`, Python compile/JS syntax sạch; production API `200`, UI đủ sáu objective, console sạch, web/worker active và PostgreSQL healthy.
- Safety: Mọi discovery draft đã xóa ở Campaign level theo exact ID/name, legitimate draft được giữ, smoke UI không lưu dữ liệu và không click Publish.

### 2026-07-31 - Phase 06 deterministic field filling

- Changed: Thêm declarative field action plan theo objective/stage, DOM adapter hỗ trợ editor lazy-rendered, per-field result contract và bảng kết quả trong job detail.
- Affected: objective catalog/schema, Meta worker runtime, campaign UI, smoke/inspection scripts, tests và project memory.
- Verified: `24 passed`, Python compile/JS syntax sạch; production Sales smoke áp dụng budget/URL, xác minh default surface, từ chối Page không exact-match và dừng `awaiting_user` tại Ad.
- Safety: `published=false`; discovery draft `6982633575177` đã được xác minh exact ID/name và xóa, campaign hợp lệ được giữ nguyên.

### 2026-07-31 - Phase 07 resource, asset và human handoff

- Changed: Thêm Meta resource registry, creative asset streaming/SHA-256, approved snapshot, worker-scoped asset download/media input, targeting cơ bản và noVNC handoff tại exact Ads Manager URL.
- Affected: campaign backend/UI, browser session contract, worker execution, migration `20260731_0004`, tests và project memory.
- Verified: `27 passed`, Python compile/JS syntax sạch; production APIs/UI smoke `200`, Alembic `head`, console sạch, web/worker/PostgreSQL healthy.
- Safety: Không tạo resource/asset giả trên account test, không tạo session/job mới, không thêm payment method và không click `Publish`.

### 2026-07-31 - Sửa cô lập Chrome profile trên Snap Chromium

- Changed: Bỏ qua `/snap/bin/chromium`, dùng direct Snap binary, thêm profile bootstrap guard và regression tests cho wrapper detection.
- Affected: browser runtime, worker env, account-session/infra memory và production cookie placement.
- Verified: `30 passed`; production main/child process đều dùng UUID profile mới, shared-path process bằng `0`, CDP trả Meta Business login page và worker/health đều active.
- Safety: Phiên sai đã đóng graceful; kho cookie chung, PG/source/env và hai profile được backup trước khi copy trạng thái lịch sử vào đúng account test.

### 2026-07-31 - Hoàn tất Phase 7 E2E đến Review

- Changed: Thêm sửa label ad account có dependency guard, UTF-8/mojibake regression, noVNC TTL 120 phút, exact Page/creative registry và Meta draft runtime cho lazy row, Page group, native file chooser cùng content wizard `Tiếp`/`Xong`.
- Affected: campaign backend/UI, worker Meta runtime, infra env, tests, production DB/resource/asset và project memory.
- Verified: `34 passed`, Python compile sạch; production web/worker `active`, health `ok`; job `e18ca3b5-aaa4-4ac7-9c2b-933701768990` đạt `review_ready` với đủ Campaign/Ad Set/Ad, media/text applied, artifact Review thật và `published=false`.
- Safety: Không thêm payment method, không click `Đăng`; các phiên noVNC khảo sát đóng sạch và production deploy có PG/source backup trước mỗi worker restart.

### 2026-08-01 - Phase 08 reporting, KPI và lịch Telegram

- Changed: Thêm report schedule/job/snapshot contract, Ads Manager read-only DOM collector, `/reports`, manual confirmation, lịch hằng ngày và Telegram delivery fail-soft; xóa hai E2E draft cũ theo exact ID và sửa display name mojibake trong DB.
- Affected: reporting backend/UI/worker, migration `20260801_0005`, tests, deploy scripts và project memory.
- Verified: `38 passed`, compile/JS syntax sạch; production Alembic `head`, web/worker active, UI console sạch; job `1dcdcabb-adeb-4359-8549-a93dee4af385` tạo snapshot thật với `ad_mutated=false`, `published=false`.
- Safety: Không có payment/publish action; hai draft xóa không thể hoàn tác nhưng draft đạt Review `120250169244880033` vẫn còn; production backup trước deploy và post-smoke dump đều đã kiểm tra.

### 2026-08-01 - Phase 08 multi-VPS fleet và AI provider

- Changed: Thêm popup SSH install/edit/drain/decommission/revoke, one-time enrollment, per-node credential, durable worker outbox và Hermes provider/API key theo worker.
- Affected: backend/API/UI, worker runtime, bootstrap/systemd, migration `20260801_0006`, tests và project memory.
- Verified: `42 passed`, Python/JavaScript/migration sạch; production Alembic `head`, web/worker active, Hermes Agent `v0.19.1` đã cài và worker hiện hữu được backfill host/install state.
- Safety: SSH password chỉ ở RAM, API key encrypted/masked, Hermes inactive tới khi có config; backup source/env/PostgreSQL tại `/opt/meta-ads-backups/20260801-125156`.

### 2026-08-01 - Git checkout và DeepSeek V4 Flash preset

- Changed: Tạo public repo `pearhoang/ads-facebook-automation`, đặt repo/branch mặc định cho worker và thêm preset DeepSeek `deepseek-v4-flash` vào Bot VPS/AI Copilot.
- Affected: Git bootstrap, backend config/UI, infra env example, production source và project memory.
- Verified: `43 passed`, Python/JavaScript sạch; production checkout tracking `origin/main`, web/worker active và health `ok`.
- Safety: `.env`, database, output, browser state và tar backup bị ignore; chưa lưu API key vì ảnh DeepSeek chỉ hiển thị masked value.
