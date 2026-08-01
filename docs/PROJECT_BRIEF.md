# Project Brief

## Purpose

- Xây dựng SaaS quản lý và tự động hóa Meta Ads qua browser cho khách hàng dùng chính Facebook/ad account của họ.
- Cung cấp dashboard tài khoản, browser session/noVNC, campaign jobs, KPI/reporting và AI copilot qua web/Telegram.
- Tái sử dụng mô hình đã vận hành ổn của `Youtube_Upload_Lush`: FastAPI control plane + outbound Python worker + persistent Chrome profile.

## System Shape

- `backend/`: FastAPI control plane, server-rendered web UI, tenant/auth, job/approval/audit APIs.
- `workers/`: Python worker chạy Chrome profile, Xvfb/Openbox/x11vnc/websockify, Playwright/CDP và debug artifacts.
- `agent/`: Hermes integration và typed tools để hiểu ý định, phân tích KPI, lập kế hoạch và browser recovery.
- `infra/`: Docker Compose, reverse proxy, service config và worker bootstrap.
- `PostgreSQL` là source of truth; worker giao tiếp outbound bằng register/heartbeat/poll/sync.

## Main Modules

- `backend/app`: control plane và API contracts.
- `workers/agent`: browser/session/job runtime.
- `agent`: Hermes gateway, skills và tool facade.
- `infra`: deploy surfaces.

## Global Invariants

- Tenant chỉ được truy cập profile, ad account, campaign, job và artifact thuộc tenant đó.
- Production tenant identity chỉ lấy từ server-side user session và active membership.
- Browser profile có đúng một owner worker và tối đa một controller tại một thời điểm.
- Chromium main/child process phải dùng exact `profile_key` path; runtime không được fallback sang Snap global user-data directory.
- noVNC chỉ mở theo phiên có token hết hạn; CDP/debug port không public.
- Core workflow dùng deterministic state machine; LLM không điều khiển từng click trong happy path.
- Sáu objective dùng catalog adapter canonical; chỉ default path đã khảo sát mới được tự động hóa.
- Mỗi field mutation phải có kết quả DOM riêng (`applied`, `already_set`, `verified`, `blocked`, `not_available`); không suy diễn thành công từ việc đã đi qua stage.
- Meta resource và creative asset phải theo tenant/ad account; approved snapshot giữ exact resource metadata và SHA-256 của asset.
- Worker chỉ tải asset qua authenticated job contract, xác minh digest và dừng `awaiting_user` khi resource chưa verified hoặc Meta cần thao tác thủ công.
- Reporting dùng job contract riêng và snapshot bất biến; browser collector chỉ đọc Ads Manager, không dùng campaign execution approval làm report state.
- Lịch báo cáo dùng ngày đã hoàn tất theo timezone ad account; Telegram token chỉ nằm ở worker environment.
- Thao tác publish, tăng budget hoặc thay đổi rủi ro cao phải qua preview, guardrail và approval.
- Agent không phải source of truth và không được sửa production trực tiếp.
- Production schema chỉ thay đổi qua Alembic revision; application startup không tự tạo bảng.

## Build / Test / Lint

- Install: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- Run backend: `.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload`
- Test: `.\.venv\Scripts\python.exe -m pytest`
- Syntax: `.\.venv\Scripts\python.exe -m compileall -q backend workers`
- Migrate: `.\.venv\Scripts\python.exe -m alembic upgrade head`
- Schema drift: `.\.venv\Scripts\python.exe -m alembic check`

## Module Boundaries

- Backend không chạy browser trong request handler.
- Worker không đọc database trực tiếp; chỉ dùng worker API contract.
- Hermes chỉ gọi typed tool facade; không giữ business state canonical.
- UI không gọi trực tiếp worker/noVNC host.

## Safety Constraints

- Không lưu password, recovery code hoặc OTP/2FA.
- Không có public signup; owner/user được provision qua admin boundary.
- Mặc định action tạo campaign ở trạng thái `DRAFT`.
- Khi UI drift, worker dừng trước mutation tiếp theo/publish và lưu artifact để recovery.
- Meta draft builder chỉ được tạo hoặc sửa entity chưa publish; `Publish` luôn nằm ngoài Phase 4-7.
- Self-improvement chỉ tạo proposal; áp dụng sau review và regression test.

## Key References

- `docs/MEMORY_INDEX.md`
- `docs/DECISIONS_INDEX.md`
- `docs/modules/account-session.md`
- `docs/modules/control-plane-worker.md`
- `docs/modules/database-migrations.md`
- `docs/modules/meta-draft-builder.md`
- `docs/modules/objective-adapters.md`
- `docs/modules/resource-asset-registry.md`
- `docs/UI_SYSTEM.md`
