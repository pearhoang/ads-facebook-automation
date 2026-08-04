# Decisions

## DEC-001 — FastAPI control plane và outbound Python worker

- Giữ mô hình đã chứng minh trong `Youtube_Upload_Lush`.
- Browser runtime nằm trên worker; backend quản lý state và contract.

## DEC-002 — Hermes là AI orchestrator

- Hermes xử lý Telegram, intent, report narrative, suggestions và recovery.
- PostgreSQL/FastAPI vẫn là source of truth.

## DEC-003 — Deterministic happy path

- Playwright/CDP state machine xử lý thao tác lặp lại.
- Chỉ gọi AI khi cần hiểu yêu cầu, phân tích hoặc xử lý UI drift.

## DEC-004 — Account Session là vertical slice đầu tiên

- Flow: tạo account/profile → phân worker → mở noVNC → user đăng nhập/2FA → confirm → đóng phiên.
- Flow này xác thực đồng thời auth ownership, worker contract và browser infrastructure.

## DEC-005 — Guardrail cho hành động rủi ro

- Campaign mới mặc định `DRAFT`.
- Publish, tăng budget và bulk mutation cần explicit approval và audit log.

## DEC-006 — Trích module thay vì fork nguyên app YouTube

- Tạo codebase mới để tránh mang theo domain upload/render/live stream.
- Tái sử dụng có chọn lọc browser runtime, worker protocol và UI patterns đã ổn định.

## DEC-007 — Test deployment dùng systemd và shared Caddy

- Web/worker chạy trực tiếp trên host để truy cập Xvfb/Chromium runtime.
- Caddy container hiện có chỉ được thêm site block, không thay đổi các upstream khỏe.

## DEC-008 — Browser traffic đi qua backend proxy

- websockify chỉ bind `127.0.0.1`; không mở port noVNC ra Internet.
- FastAPI proxy HTTP/WebSocket theo browser session còn hiệu lực.

## DEC-009 — Production auth dùng opaque server-side session

- Password dùng Argon2; database chỉ giữ hash password và digest của session/CSRF token.
- Secure cookie xác định user session; tenant lấy từ active membership, không nhận từ client header.
- Self-service đổi mật khẩu giữ phiên hiện tại và revoke các phiên khác của user; endpoint bắt buộc authenticated session và matching CSRF token.
- User mutation API yêu cầu CSRF token; browser WebSocket kiểm tra tenant và canonical origin.
- Không mở public signup; owner được provision qua CLI admin boundary.

## DEC-010 — PostgreSQL và Alembic là production database boundary

- Dùng dedicated PostgreSQL 17.10 container, chỉ bind `127.0.0.1:55432` và persistent host volume.
- Alembic quản lý mọi production schema revision; app startup không gọi `create_all` ở production.
- Lần cutover đầu copy transactional toàn bộ SQLite rows, giữ SQLite snapshot và tạo verified `pg_dump`.
- Worker tiếp tục outbound HTTP contract, không được truy cập trực tiếp PostgreSQL.

## DEC-011 — Approval nội bộ tách khỏi publish execution

- Phase 2 kết thúc ở trạng thái `approved`; không có side effect lên Meta.
- Approval request giữ snapshot theo campaign version để người duyệt thấy đúng budget, schedule, targeting và creative đã submit.
- Publish sau này phải là job/action riêng, có preview và approval/guardrail tương ứng; không tự động chạy chỉ vì campaign đã approved.

## DEC-012 — Phase 3 chỉ chạy deterministic read-only preflight

- Execution job đầu tiên dùng persistent Chrome profile nhưng chỉ điều hướng, đọc state bằng CDP và chụp screenshot.
- User phải confirm riêng sau approval; campaign approved không tự enqueue job.
- Browser session và preflight lock loại trừ nhau trên cùng profile.
- `allow_click=false` và `allow_publish=false` là contract bắt buộc; live publish là phase/decision riêng.

## DEC-013 — Phase 4 chỉ mutation trên unpublished Meta draft

- Draft builder dùng deterministic CDP state machine theo thứ tự `Campaign → Ad Set → Ad → Review`.
- Job chỉ được tạo sau khi cùng campaign version đã có preflight thành công và người dùng nhập đúng `TẠO DRAFT META`.
- Payload bắt buộc `mode=draft_only`, `allow_click=true`, `allow_publish=false`, `stop_before=publish`.
- Worker tạo mới hoặc resume đúng draft của campaign; không nhân bản draft khi retry.
- Mỗi bước lưu screenshot checkpoint. Khi thiếu Page/creative hoặc UI drift, job chuyển `awaiting_user`/`failed` và dừng trước mutation tiếp theo.
- Nút `Đăng`/`Publish` không được click trong Phase 4; publish phải là action và quyết định riêng.

## DEC-014 — Objective automation dùng catalog adapter canonical

- `backend/app/services/objective_specs.py` là canonical source cho sáu objective đã khảo sát; UI lấy catalog qua authenticated API và backend snapshot adapter vào draft job.
- Worker dùng deterministic adapter cho default path. Traffic chọn setup thủ công; conversion location khác default bị block cho đến khi có adapter riêng.
- Required/warning field được tính theo objective, không áp dụng destination URL cho mọi campaign.
- Retry chỉ resume exact campaign name để tránh chạm draft Meta mặc định hoặc campaign ngoài job.
- Adapter không thay đổi guardrail: mọi mutation vẫn unpublished và worker không click `Đăng`/`Publish`.

## DEC-015 — Field filling dùng declarative stage plan và kết quả DOM đã xác minh

- Mỗi objective adapter khai báo `field_actions` theo Campaign/Ad Set/Ad; worker không tự đoán handler hoặc entity value ngoài approved snapshot.
- Meta editor lazy-rendered được quét bằng vùng scroll nội bộ; status chỉ thành công khi control nhận giá trị hoặc surface đúng được nhìn thấy trên DOM.
- Worker lưu `field_results` cho từng field. `blocked`, `not_available` và `failed` phải hiện cho user và dừng trước Publish nếu field required/terminal.
- Entity selector như Page, Instant Form, app, dataset và conversion event bắt buộc exact-match; không chọn lựa chọn đầu tiên làm fallback.
- Phase 6 vẫn là unpublished draft-only: `allow_publish=false`, không có code path click `Đăng`/`Publish`.

## DEC-016 — Resource exact-match, asset digest và human handoff trước Review

- Page, Instagram account, Dataset/Pixel, Instant Form và App được lưu theo tenant/ad account; resource mới luôn `unverified` cho đến khi user/admin nhập confirmation rõ ràng sau khi đối chiếu Meta.
- Campaign snapshot giữ resource label/external ID/status và creative asset SHA-256; worker chỉ tải asset được job của chính worker tham chiếu và phải xác minh digest trước upload.
- Creative asset được stream vào generated path, kiểm tra extension, MIME, magic bytes và giới hạn dung lượng; không dùng user filename làm storage path.
- Khi Meta yêu cầu dữ liệu/chọn lựa/xác minh thủ công, job dừng `awaiting_user`; noVNC chỉ được mở tại HTTPS URL thuộc `*.facebook.com` và Ads Manager.
- Payment method không được giả lập và `Publish` vẫn không có executor. Tài khoản test có thể kiểm tra toàn bộ control plane nhưng không được coi là end-to-end live ad.

## DEC-017 — Snap Chromium phải chạy direct binary và chứng minh profile path riêng

- Không chạy account session qua `/snap/bin/chromium`; snap launcher ép child process về `/root/snap/chromium/common/chromium` và làm rò cookie giữa các `profile_key`.
- Worker ưu tiên `/snap/chromium/current/usr/lib/chromium-browser/chrome` và vẫn truyền exact `--user-data-dir=<profile_root>/<profile_key>`.
- Launch chỉ thành công khi `Local State` được tạo trong exact profile path; nếu không, runtime dừng Chromium/Xvfb/Openbox và trả lỗi thay vì mở noVNC dùng profile chung.
- Production migration chỉ sao chép snapshot kho cookie chung vào profile của account test lịch sử; profile account mới phải giữ sạch và có cookie database riêng sau lần launch đầu.

## DEC-018 — Reporting dùng read-only worker job và immutable snapshot

- Reporting có contract riêng gồm schedule, job và immutable snapshot; không gắn report state vào campaign approval/execution job.
- Worker dùng đúng persistent Chrome profile, không chạy khi browser session hoặc execution job đang giữ profile, và chỉ sync snapshot khi có `ad_mutated=false`, `published=false`.
- Schedule tạo job hằng ngày theo timezone ad account và dùng các ngày đã hoàn tất; worker poll là scheduler boundary hiện tại.
- Telegram chat ID có thể lưu theo schedule/job nhưng bot token chỉ nằm trong worker environment. Thiếu token hoặc gửi lỗi chỉ đổi delivery status; snapshot KPI vẫn được giữ.
- Hermes sẽ dùng snapshot để tạo narrative/suggestion ở phase AI; deterministic collection/delivery không biến Hermes thành source of truth.

## DEC-019 — Multi-VPS fleet dùng per-node identity và durable worker state

- Mỗi worker enroll bằng token một lần và nhận credential riêng; credential node A không được điều khiển node B.
- Worker giữ assignment cache và outbox trong local SQLite để tiếp tục công việc đã claim khi control-plane gián đoạn rồi replay idempotent khi kết nối lại.
- `Drain` ngừng cấp job mới; `Revoke` vô hiệu credential nhưng giữ row/audit. Decommission mặc định gỡ service, không xóa browser profile.
- Worker systemd không `Requires` web service cùng máy; mọi giao tiếp với control-plane vẫn outbound HTTPS.

## DEC-020 — SSH secret transient và AI provider scope theo worker

> Phần SSH password transient đã được thay thế bởi DEC-027. Telegram bootstrap token và các nguyên tắc provider scope trong quyết định này vẫn còn hiệu lực.

- Popup install/decommission nhận SSH password nhưng chỉ truyền vào background job trong RAM; không ghi DB, operation message, response hoặc audit.
- Lần cài đầu ghi SSH host fingerprint; decommission từ xa phải khớp fingerprint đã lưu nếu có.
- AI API key mã hóa bằng `SECRET_ENCRYPTION_KEY`; UI/API chỉ trả masked hint, còn raw key chỉ được giải mã cho đúng worker credential.
- Add Bot nhận Telegram Bot Token và allowlist trong cùng request. Token chỉ đi qua file tạm SSH mode `0600`, được ghi vào worker env mode `0600`, rồi file tạm bị xóa; control-plane không lưu token/allowlist trong DB, audit, response hay command line.
- Hermes service không tự chạy chỉ vì đã cài; worker chỉ enable/start sau khi nhận provider base URL, model và key hợp lệ.

## DEC-021 — Public Git checkout là source bootstrap canonical

- Canonical source là `https://github.com/pearhoang/ads-facebook-automation.git`, branch `main`.
- Repository public để worker bootstrap clone không cần lưu GitHub token/SSH key trên control-plane hoặc VPS.
- Popup cài worker điền sẵn canonical repo nhưng cho phép owner thay URL/branch khi triển khai fork riêng.
- Production `/opt/meta-ads-copilot` phải là checkout sạch tracking `origin/main`; runtime data, env và secret luôn nằm ngoài Git.

## DEC-022 — Telegram là conversational gateway, action chỉ qua typed tools

- Telegram message đi vào Hermes gateway theo session hội thoại; slash command chỉ là tiện ích, không phải giao diện chính.
- Hermes chỉ truy cập dữ liệu Ads Lush qua MCP stdio bridge dùng per-node credential; legacy shared secret không được gọi agent tools.
- Tool mutation duy nhất ở phase này tạo control-plane `DRAFT`; không có tool submit approval, chạy browser, tăng budget hoặc publish.
- Telegram allowlist bắt buộc. Gateway không được bật `allow all`; token ở worker environment và không trả qua UI/API.
- Telegram toolset production tắt terminal, file, browser, code execution, delegation và computer use; browser ads vẫn do deterministic worker state machine sở hữu.
- Reasoning lưu theo worker. `thinking_mode=disabled` ánh xạ thành Hermes `reasoning_effort=none`; provider-specific thinking payload chỉ gửi cho endpoint đã nhận diện hỗ trợ.

## DEC-023 — AI Copilot dùng Hermes session bridge và chỉ phục vụ Meta Ads

- AI Copilot không tự xây inference/chat engine; worker gọi Hermes API Server local và control-plane chỉ giữ tenant-scoped mirror cùng outbound job state.
- Web và Telegram tiếp tục cùng exact `hermes_session_id`, nên lịch sử/ngữ cảnh không bị tách thành hai trợ lý.
- Natural language là luồng mặc định. Shortcut chỉ là tối đa hai tiện ích cho action preview/resource cụ thể và không vô hiệu composer.
- Slash shortcut trên Web là command palette cục bộ (`/help`, `/new`, `/sync`, `/status`), không giả lập messaging command của Hermes API Server và chỉ xuất hiện khi user gõ `/`.
- Web chỉ nhận tối đa ba tệp text/data UTF-8 (TXT, MD, CSV, JSON, YAML/YML), không persist binary và gửi nội dung sang Hermes như untrusted reference data. Image/PDF chờ vision/document pipeline thật.
- Transcript public chỉ gồm `user|assistant`; `tool|session_meta`, raw MCP schema và untrusted tool result là runtime nội bộ. Assistant Markdown được render bằng safe DOM subset, không chấp nhận raw HTML.
- Provider/model settings có canonical surface riêng `Hermes Agents`; popup sửa Bot VPS không lặp lại cấu hình này.
- Không tích hợp VPS Copilot vào sản phẩm Ads. Chat quản trị máy chủ nằm ngoài scope SaaS hiện tại.
- Hermes API Server bind localhost, bearer key chỉ nằm trên worker; control-plane/JavaScript không nhận key.
- Provider credential nằm trong Hermes home `.env` và phải được systemd nạp cùng worker env để Telegram và API Server dùng chung provider runtime.
- Hermes API Server giữ virtual model `ads-copilot`, nhưng route này phải nằm trong `gateway.api_server.extra.model_routes` và trỏ tới exact named provider/model của từng worker.

## DEC-024 — Hermes permission mode theo worker và opt-in Experimental Full Access

- `agent_permission_mode=ads_safe` là mặc định cho worker mới và giữ terminal, file, browser, code execution, delegation cùng computer use trong `agent.disabled_toolsets`.
- Owner có thể bật `experimental_full` riêng cho một worker tại `Hermes Agents`; worker gỡ đúng sáu block do Ads Lush quản lý và có thể đảo ngược về `Ads Safe`.
- Full access nhằm thử nghiệm khả năng tạo artifact, chạy code, dùng browser/computer và tự xây skill sau khi kiểm thử. Nó không cấp typed tool submit approval, publish hoặc tăng budget và không được dùng quyền hệ thống để đi vòng safety boundary của Meta Ads.
- API key, Telegram token và worker credential tiếp tục là secret; thao tác phá hủy, thay đổi hệ thống, cài package toàn cục hoặc gửi dữ liệu ra ngoài phải có xác nhận rõ ràng.
- Thay đổi toolset áp dụng cho session mới hoặc sau `/reset`; web/Telegram vẫn dùng chung Hermes runtime của worker.

## DEC-025 — Chat Web dùng native Hermes Dashboard

- Không tiếp tục duy trì AI Copilot chat UI tự xây vì nó cần outbound polling/sync thủ công và chỉ lặp một phần nhỏ khả năng của Hermes.
- Telegram là kênh trò chuyện/ra lệnh chính; người dùng cần Web chat, session, file, skill, cron hoặc monitoring sẽ dùng native Hermes Dashboard.
- Route `/ai-copilot` vẫn yêu cầu Ads Lush session rồi chuyển hướng tới dashboard; legacy API, transcript và job table được giữ để rollback, không hard-delete dữ liệu.
- Dashboard chạy service riêng từ cùng `HERMES_HOME`, bind interface nội bộ, dùng password provider chính chủ với scrypt hash + signing secret và được Caddy expose qua HTTPS subdomain.
- `Hermes Agents` tiếp tục là canonical control-plane UI cho provider/model/thinking/permission; nó không nhúng hoặc tái tạo chat.
- Owner xoay mật khẩu Dashboard theo worker bằng SSH credential đã mã hóa theo DEC-027; control-plane không trả plaintext, worker thay scrypt hash và signing secret rồi chỉ restart dashboard service để thu hồi mọi phiên Dashboard cũ.

## DEC-026 — Search/vision fallback dùng per-worker Codex OAuth và Hermes MCP

- DeepSeek tiếp tục là inference provider chính; `codex_search` và `codex_vision` chỉ là fallback read-only khi cần dữ liệu web mới hoặc phân tích ảnh.
- Hai extension tham khảo trong `pearhoang/pi-setup` là Pi SDK extension và đọc `~/.codex/auth.json`; hệ thống không cài thêm Pi agent mà reimplement search/OAuth contract thành Python MCP cho Hermes.
- Kết nối dùng official `codex login --device-auth` theo từng worker. User mở public verification URL và nhập one-time code trên trình duyệt riêng, không cần noVNC.
- Credential ở `<WORKER_DATA_DIR>/codex/auth.json` mode `0600`; control-plane chỉ thấy trạng thái không nhạy cảm qua heartbeat và không lưu cookie, access token hoặc refresh token.
- `codex_vision` chỉ đọc ảnh trong các worker/Hermes data root cho phép; tool không cấp thêm Meta mutation, publish hoặc budget permission.

## DEC-027 — Lưu SSH credential mã hóa theo worker

- `Add Bot` nhận SSH password một lần và mã hóa bằng Fernet với `SECRET_ENCRYPTION_KEY`; enrollment chuyển ciphertext sang worker sau khi kết nối thành công.
- `Sửa thiết lập` có thể rotate password; để trống giữ ciphertext hiện tại. API/UI chỉ trả `ssh_password_configured`, không trả plaintext hoặc ciphertext.
- Decommission, đổi password Hermes Dashboard và Codex connect/disconnect giải mã credential ngay trước background task; plaintext chỉ tồn tại trong RAM và không ghi vào audit, operation message hay log.
- Revoke worker xóa ciphertext. Telegram Bot Token vẫn là bootstrap secret transient và không thuộc cơ chế lưu SSH này.
- Worker được enrollment thủ công có thể chưa có credential; remote action phải trả `409` và yêu cầu owner lưu password tại `Bot VPS -> Sửa thiết lập`.
