# phase-01-account-session Account Session Vertical Slice

## Goal

- Chạy được flow xuyên suốt từ web control plane tới worker và phiên Chrome/noVNC cho một Facebook account.

## Scope

- Project scaffold.
- Tenant/user tối thiểu cho local development.
- Worker register/heartbeat.
- Account/profile CRUD tối thiểu.
- Browser session request/poll/sync/confirm/close contract.
- Fake runtime test trước, real Linux runtime sau.

## Constraints

- Không kéo domain YouTube upload/render/live stream vào repo mới.
- Không thêm Hermes hoặc campaign automation trước khi session foundation ổn định.
- Không lưu Facebook credential hoặc 2FA.

## Current State

- Kiến trúc và boundary đã chốt.
- Đã xác định reusable source trong `Youtube_Upload_Lush`.
- Đã scaffold FastAPI, SQLAlchemy và outbound worker contract.
- Đã có state machine `requested → starting → awaiting_user → ready → closing → closed`.
- Đã có worker assignment, active-session uniqueness và tenant isolation test.
- Đã port browser runtime Chromium/Xvfb/Openbox/x11vnc/websockify.
- Đã có backend HTTP/WebSocket proxy nên noVNC không mở public port.
- Đã deploy web + worker lên `82.197.71.6` và kiểm thử UI thực tế.
- Đã kích hoạt DNS, HTTPS và noVNC WebSocket trên `https://ads.lushmedia.net`.
- Đã thay Caddy Basic Auth và `X-Dev-Tenant-ID` bằng user/session/tenant auth thật.
- Đã cutover SQLite sang PostgreSQL 17.10 và quản lý schema bằng Alembic.
- Phase 01 đã hoàn tất; regression suite toàn repo hiện tại: `9 passed`.

## Next Steps

- Thêm UI quản trị user/invite/password reset và tenant-worker assignment.
- Phase 02 đã triển khai; bước tiếp theo là chốt Phase 03 execution contract.

## Risks

- Carry-over debt nếu copy nguyên `store.py` hoặc worker main loop cũ.
- noVNC access control và concurrent profile ownership.
- Browser session chờ user lâu hơn job lease thông thường.
