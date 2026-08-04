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

### 2026-08-01 - Xác nhận DeepSeek V4 Flash 0731

- Changed: Đổi nhãn preset thành DeepSeek V4 Flash 0731 nhưng giữ API model ID canonical `deepseek-v4-flash` theo live `/models`.
- Verified: DeepSeek `/models` và Chat Completions trả `200`; non-thinking smoke trả `OK`, Hermes/web/worker active.
- Safety: Raw key không xuất hiện trong log/response; DB chỉ giữ ciphertext và masked hint.

### 2026-08-01 - Phase 09 Telegram, Hermes và typed tools

- Changed: Thêm thinking/reasoning theo worker, Telegram conversational gateway, MCP bridge và năm typed tools cho workspace/KPI/report/campaign draft.
- Affected: AI provider schema/UI, worker Hermes config, worker API, systemd/bootstrap, tests và project memory.
- Verified: `45 passed`, Python compile, JavaScript syntax và Alembic schema check sạch; production migration `head`, web/worker/Hermes active, MCP handshake khám phá 5 tools và natural-language one-shot đọc đúng workspace cùng 2 ad accounts.
- Safety: Agent tools yêu cầu per-node credential; terminal/file/browser/code execution bị tắt và campaign tool chỉ tạo `DRAFT`, không submit hoặc publish.

### 2026-08-01 - Sửa environment isolation của Hermes MCP

- Changed: Forward rõ ràng `CONTROL_PLANE_URL`, `WORKER_DATA_DIR` và `WORKER_CREDENTIAL_FILE` vào MCP subprocess; tăng managed config schema để mọi worker tự refresh.
- Verified: Hermes `mcp test` kết nối trong 415 ms và khám phá đủ 5 tools; Telegram gateway/outbound message đạt, config không chứa raw node credential.
- Safety: Chỉ forward ba biến tối thiểu; raw credential tiếp tục nằm trong file quyền `0600`.

### 2026-08-01 - Phase 10 Ads Copilot và one-shot Add Bot

- Changed: Biến AI Copilot thành chat Meta Ads natural-first dùng exact Hermes session chung với Telegram; tách provider sang Hermes Agents; Add Bot nhận đủ Git checkout, provider, Telegram token và allowlist để tự bootstrap worker/noVNC/Hermes.
- Affected: agent conversation/job backend, outbound Hermes API bridge, AI Copilot/Hermes Agents/Bot VPS UI, migration `20260801_0008`, bootstrap installer, tests và project memory.
- Verified: `47 passed`, Python compile, JavaScript và installer syntax sạch; production migration `20260801_0008 (head)`, web/worker/Hermes active, public health `ok`, Hermes API chỉ bind `127.0.0.1:8642`, có 1 Telegram session và không có error log sau deploy.
- Safety: Không có VPS Copilot; không gửi tin nhắn/publish/budget action trong smoke test. Telegram token đi qua file tạm SSH `0600`, không nằm trong command line/database/audit/response; backup tại `/var/backups/meta-ads-copilot/20260801T140223Z`.

### 2026-08-01 - Sửa transcript và session layout của Ads Copilot

- Changed: Ẩn role Hermes nội bộ `tool|session_meta`, render assistant Markdown bằng safe DOM subset, khóa page scroll và thêm request guard khi đổi session.
- Affected: Copilot message API, chat JavaScript/CSS/template, tests và project memory.
- Verified: `47 passed`, Python/JavaScript sạch; local UI giữ 2/2 session sau chuyển, `window.scrollY=0`, Markdown table/list/bold render đúng và console không lỗi. Production trả public role đúng `assistant,user`, technical message bằng `0`, web/worker/Hermes active và health `ok`.
- Safety: Không xóa transcript cũ; tool message lịch sử chỉ bị ẩn khỏi user API. Không restart worker/Hermes, không gửi chat, không tạo campaign; backup tại `/var/backups/meta-ads-copilot/20260801T142205Z-copilot-ui`.

### 2026-08-01 - Khôi phục Web chat và thêm attachment/slash shortcut

- Changed: Nạp Hermes provider `.env` vào systemd, che lỗi localhost khỏi public API, thêm attachment text/data UTF-8 và command palette `/help|/new|/sync|/status` cho AI Copilot.
- Affected: Hermes service/worker bridge, Copilot message contract/service/UI, tests và project memory.
- Verified: `51 passed`, Python compile, JavaScript syntax, UTF-8 guard và local browser verification đạt; palette chỉ hiện khi gõ `/`, attachment queue không gây page scroll và console không lỗi.
- Safety: Không giả hỗ trợ image/PDF; binary không persist, attachment được đánh dấu untrusted data và giới hạn 3 tệp/256 KB tổng. Production verification được ghi sau deploy.

### 2026-08-01 - Sửa provider route của Hermes Web session

- Changed: Ánh xạ virtual model `ads-copilot` qua `gateway.api_server.extra.model_routes` tới exact named provider/model của worker; tăng managed Hermes config schema để mọi worker tự áp dụng.
- Affected: `workers/agent/hermes_config.py`, provider regression test và project memory.
- Verified: `51 passed`, compile/diff sạch; production Hermes session tạo với model `ads-copilot` và chat trả `200`, session smoke được xóa; web/worker/Hermes active, public health `200`, current Hermes invocation có `0` provider/runtime error và Alembic không có drift.
- Safety: Không tạo campaign, không publish, không giữ session smoke; production không có active agent job hoặc browser session khi deploy.

### 2026-08-01 - Gọn attachment trigger trong AI Copilot

- Changed: Đổi nút chữ `Đính kèm` thành dấu `+` nằm trong mép trái ô chat, giữ tooltip, accessible label và attachment queue hiện có.
- Affected: AI Copilot template/CSS, UTF-8 UI regression test và UI system memory.
- Safety: Không đổi upload API, loại tệp, giới hạn dung lượng hoặc Hermes message flow.

### 2026-08-01 - Experimental Full Access theo từng Hermes Agent

- Changed: Thêm `agent_permission_mode` theo worker, UI `Ads Safe | Experimental Full Access`, audit/runtime contract và worker sync có thể gỡ/khôi phục sáu toolset block terminal/file/code/browser/computer/delegation.
- Affected: AI provider schema/API/UI, Alembic `20260801_0009`, Hermes config/SOUL, tests và project memory.
- Verified: `53 passed`, Python compile, JavaScript syntax, UTF-8 guard và Alembic `20260801_0009 (head)` sạch. Production worker `Ads Browser VPS 82` đã ghi audit `experimental_full`; `disabled_toolsets` rỗng và smoke session dùng thật `terminal` + `read_file`, trả `/root`, Python 3.12.3 và Ubuntu 24.04.4 LTS rồi được xóa.
- Deploy: Commit `82835ed`, web/worker/Hermes active, public health `ok`, API Server chỉ bind `127.0.0.1:8642`; backup tại `/var/backups/meta-ads-copilot/20260801T165330Z-experimental-full`.
- Safety: Worker mới vẫn mặc định `Ads Safe`; full access không thêm typed tool publish/budget và không thay DRAFT/approval boundary của control-plane.

### 2026-08-02 - Chuyển Web chat sang native Hermes Dashboard

- Changed: Retire AI Copilot UI tự xây khỏi navigation; route cũ chuyển hướng có authentication sang native Hermes Dashboard. Thêm dashboard systemd unit, HTTPS Caddy route và action mở dashboard tại Hermes Agents.
- Affected: web route/config, navigation templates, Hermes/Caddy packaging, tests, decisions và module memory.
- Verified: `54 passed`, Python/JavaScript/UTF-8/diff check sạch. Production HTTPS dùng Let's Encrypt; basic-auth login, Telegram session list, Chat PTY và tool event feed đều hoạt động. Smoke chat trả đúng `HERMES DASHBOARD OK` và session thử đã được xóa.
- Deploy: Commit UI/infra `7381070`, WebSocket proxy fix `3164426`; web/worker/Hermes gateway/dashboard đều active. Port `9119` chỉ bind `172.17.0.1`. Backup tại `/var/backups/meta-ads-copilot/20260801T171727Z-native-hermes-dashboard` và `/opt/spoticheck/app/deploy/Caddyfile.pre-hermes-ws-20260801T173809Z`.
- Safety: Không xóa transcript, AgentJob, API hoặc migration legacy; dashboard dùng Hermes auth provider, bind nội bộ và không expose port `9119` trực tiếp.

### 2026-08-02 - Self-service đổi mật khẩu control-plane

- Changed: Thêm action `Đổi mật khẩu` tại footer `Lush Media`, dialog dùng chung và endpoint xác minh mật khẩu hiện tại trước khi cập nhật Argon2 hash.
- Affected: auth schema/service/API, năm trang control-plane, shared UI/JavaScript, auth tests và project memory.
- Verified: `55 passed`, Python compile, JavaScript syntax và diff check sạch. Production health/login/static asset đều trả `200`; route live có endpoint password và worker poll tiếp tục `200` sau restart.
- Deploy: Commit `d7f73de`; chỉ restart `meta-ads-copilot-web.service`, không restart worker/Hermes/noVNC. Backup tại `/var/backups/meta-ads-copilot/20260801T175642Z-control-plane-password`.
- Safety: Password không ghi vào database/log dưới dạng plaintext; form xóa secret sau response và không có public reset/recovery flow.

### 2026-08-02 - Xoay mật khẩu Hermes Dashboard theo worker

- Changed: Thêm action tại `Hermes Agents`, API owner/CSRF và remote operation qua SSH để thay scrypt hash cùng signing secret của native Dashboard.
- Affected: Bot VPS schema/API/remote ops, Hermes Agents UI, fleet tests, decision và module memory.
- Verified: `58 passed`, Python compile, JavaScript syntax và diff check sạch; scrypt contract khớp Hermes và host fingerprint mismatch bị chặn trước bước SSH authentication.
- Deploy: Commit `c13f420`; chỉ restart web control-plane. Public health `200`, route unauthenticated trả `401`, dashboard `overall=ok`, basic auth vẫn bật và bốn service đều active. Backup tại `/var/backups/meta-ads-copilot/20260801T180712Z-hermes-dashboard-password`.
- Safety: SSH password và Dashboard password chỉ tồn tại trong request/background memory; operation/database/audit không giữ plaintext. Chỉ dashboard service bị restart, còn Hermes gateway, Telegram và browser worker giữ nguyên.

### 2026-08-02 - Đăng nhập control-plane bằng username

- Changed: Login UI dùng `Tài khoản` thay cho `Email`, chấp nhận username text, cho phép password từ 4 ký tự và đổi production owner identifier thành `admin` mà không phá field API legacy.
- Affected: auth copy/template, auth regression và project memory.
- Verified: `58 passed`, Python compile, JavaScript syntax, UTF-8/diff check sạch. Production login `admin` trả `200`, identifier email cũ trả `401`, `/api/auth/me` trả `admin` và logout smoke trả `204`.
- Deploy: Commit `339dc44`; chỉ restart web control-plane, sau đó cập nhật exact owner và revoke phiên cũ. Verified source/database backup tại `/var/backups/meta-ads-copilot/20260801T183742Z-username-login`.
- Safety: Giữ Argon2 hash, CSRF, secure session cookie, tenant/role và API contract; các phiên cũ được thu hồi khi cập nhật credential production.

### 2026-08-02 - Mật khẩu Hermes Dashboard tối thiểu 4 ký tự

- Changed: Hạ validation UI/API đổi mật khẩu native Hermes Dashboard từ 12 xuống 4 ký tự theo cấu hình single-customer.
- Affected: Bot VPS schema, Hermes Agents dialog, fleet regression và project memory.
- Verified: `58 passed`; đăng nhập Hermes mới `admin / 1234` trả `200`, API session đã xác thực trả `200`, mật khẩu cũ trả `401` và Dashboard health `overall=ok`.
- Deploy: Commit `aadd2b1`; password rotation operation thành công, chỉ restart Hermes Dashboard. Source/database backup tại `/var/backups/meta-ads-copilot/20260801T184243Z-hermes-password-1234`.
- Safety: Password at rest vẫn là scrypt hash; khi đổi vẫn xoay signing secret để thu hồi phiên Dashboard cũ và không restart gateway/Telegram/browser worker.

### 2026-08-04 - Codex Search & Vision fallback cho Hermes

- Changed: Lưu SSH password quản trị dưới dạng Fernet ciphertext theo worker để Add Bot chỉ nhập một lần; Edit Bot VPS có thể rotate, revoke xóa credential và mọi remote operation chỉ giải mã trong RAM.
- Changed: Codex connect/disconnect, đổi mật khẩu Hermes Dashboard và decommission dùng SSH credential đã lưu; UI/API chỉ hiển thị cờ đã/chưa cấu hình và không trả secret.
- Added: Alembic `20260804_0010` thêm `ssh_password_ciphertext` cho worker/enrollment.
- Changed: Thêm lifecycle `Ngắt kết nối Codex` theo worker, xóa exact OAuth credential qua SSH operation transient, chặn refresh race bằng local marker và cho phép device login lại bằng account khác mà không restart Hermes/Telegram/browser.
- Fixed: Device login parser nhận đúng mã Codex CLI 9 ký tự dạng `XXXX-XXXXX`; popup tách mã xác thực thành khối dễ đọc với action `Sao chép mã`, vẫn hỗ trợ format legacy 8 ký tự.
- Changed: Thêm per-worker Codex device login tại `Hermes Agents`, heartbeat status và MCP tools `codex_search`/`codex_vision`; bump managed Hermes config schema để worker hiện hữu nhận tool dù provider không đổi.
- Affected: Bot VPS remote operation, worker heartbeat/config, Hermes MCP/SOUL, installer, UI, tests và project memory.
- Verified: `67 passed`, Python compile, JavaScript syntax, UTF-8/diff check và Alembic fresh-head check sạch.
- Safety: Không tạo ChatGPT browser profile hoặc lưu cookie/token ở control-plane; OAuth chỉ ở worker mode `0600`, tools read-only và không thay Meta DRAFT/approval/publish boundary.
- Deploy: Production đang chạy commit `be2057b`; backup nền tại `/var/backups/meta-ads-copilot/20260804T-codex-search-vision` và backup trước sửa popup tại `/var/backups/meta-ads-copilot/20260804T-codex-device-code-popup`. Codex CLI `0.146.0`, bốn service web/worker/Hermes active và `/health` trả `ok`; smoke thực tế chờ owner hoàn tất lại `device login` trên UI.

### 2026-08-03 - Đổi nhận diện control-plane sang Ads Meta Master

- Changed: Đổi visible brand thành `Ads Meta Master`, subtitle `Meta Ads Automation`, thêm custom SVG monogram `M` dùng chung cho sidebar/login/favicon và rút gọn footer còn `Admin` với action `Đổi mật khẩu`.
- Affected: Bảy Jinja template, shared workspace/auth CSS, static brand asset, auth integration test và UI system memory.
- Verified: `59 passed`, Python compile sạch, local `/health` trả `200`; browser smoke xác nhận title, brand, subtitle, footer và favicon trên `http://127.0.0.1:8010/`.
- Deploy: Chưa push hoặc deploy; thay đổi chỉ nằm trên branch local `codex/ads-meta-master-branding`.
- Safety: Giữ nguyên domain, tenant database, cookie `ads_lush_*`, API/worker contract và toàn bộ runtime/deployment identifiers.

### 2026-08-03 - Chuyển tone UI sang Meta Balanced

- Changed: Thay action/focus cam bằng Meta blue, chuyển safety/approval/warning vàng sang indigo, giữ success green và danger red; light surfaces dùng cool blue-gray, sidebar dark neutral giữ nguyên.
- Affected: Shared workspace tokens, auth/Copilot light surfaces, theme integration test và UI system memory.
- Verified: `60 passed`, Python compile và diff check sạch; local browser smoke trên Workspace, Campaigns và Hermes Agents xác nhận primary `rgb(24, 119, 242)`, indigo safety `rgb(238, 242, 255)`, danger `rgb(184, 58, 58)` và sidebar giữ `rgb(36, 35, 33)`.
- Deploy: Chưa push hoặc deploy; local preview tiếp tục chạy tại `http://127.0.0.1:8010` trên branch `codex/ads-meta-master-branding`.
- Safety: Không đổi layout, copy, API, database, worker contract, runtime identifier hoặc deployment config.

### 2026-08-03 - Deploy Ads Meta Master và Meta Balanced lên production

- Changed: Fast-forward `main` qua bộ nhận diện `Ads Meta Master` và palette Meta Balanced blue-indigo-green, sau đó triển khai lên `https://ads.lushmedia.net`.
- Affected: Jinja templates, shared workspace/auth/Copilot CSS, SVG brand asset và project UI memory; không có migration hoặc dependency mới.
- Verified: `60 passed`, Python compile và diff check sạch; production checkout sạch tại commit `33ae3d9`, health `ok`, bốn service active. Browser live xác nhận title/brand/subtitle/footer/favicon mới, accent `#1877f2`, body `rgb(243, 246, 251)`, sidebar giữ `rgb(36, 35, 33)` và không có console warning/error.
- Deploy: Push `main` từ `bf32cf4` lên `33ae3d9`; chỉ restart `meta-ads-copilot-web.service`. Source backup tại `/opt/meta-ads-copilot-runtime/source-backups/meta-ads-ui-predeploy-20260803T044448Z.tar.gz`.
- Safety: Preflight không có browser session active hoặc job queued/running; PostgreSQL healthy. PID worker và Hermes giữ nguyên, không đổi API, database, worker contract hoặc runtime config.
