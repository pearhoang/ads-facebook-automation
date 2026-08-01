# Phase 8 - Multi-VPS Fleet And AI Provider Settings

## Goal

- Quản lý nhiều Bot VPS từ control-plane thay vì cố định một worker.
- Cấp one-time enrollment token để VPS tự bootstrap, đăng ký và reconnect bằng credential riêng.
- Giữ worker outbound-only; SSH password chỉ tồn tại trong RAM của background install/decommission job và không lưu DB/log/audit.
- Cho worker hoàn tất assignment đã claim, lưu outbox cục bộ và sync lại sau khi control-plane phục hồi.
- Cấu hình Hermes provider/API key theo tenant, hỗ trợ provider trực tiếp và OpenAI-compatible gateway.

## Safety Contract

- `Drain` ngừng cấp job mới nhưng không xóa profile hoặc job đang chạy.
- `Revoke` vô hiệu hóa credential và loại node khỏi scheduler nhưng giữ audit row.
- `Decommission` được owner gọi từ popup sau `Drain`; control-plane SSH tới đúng host/fingerprint để gỡ service nhưng mặc định giữ browser profiles/data.
- Enrollment token dùng một lần, hết hạn và chỉ lưu SHA-256 digest.
- AI API key mã hóa at-rest; response không bao giờ trả raw key.
- noVNC, CDP và VNC tiếp tục bind localhost, không public trực tiếp.

## Implementation Slices

- [x] Schema/Alembic cho fleet enrollment, per-node credential, operation và AI provider config.
- [x] Owner API cho remote install/edit/drain/decommission/revoke và masked AI settings.
- [x] Worker auth per-node, heartbeat metadata, durable local outbox/reconnect.
- [x] Canonical bootstrap/decommission scripts cài browser runtime, noVNC và Hermes.
- [x] UI `Bot VPS` dạng danh sách với popup cài/sửa/gỡ/xóa và `AI Copilot` theo worker.
- [x] Automated tests, migration drift check, production deploy và smoke test không tạo ad spend.

## Acceptance

- Owner tạo được one-time install command và token không xuất hiện lại sau lần tạo.
- Node enroll nhận credential riêng; credential của node A không gọi được route của node B.
- Drain/revoke có audit và không hard-delete worker row.
- AI key lưu encrypted, GET chỉ trả hint/masked value, có thể đổi provider/base URL/model.
- Worker service không phụ thuộc `meta-ads-copilot-web.service` cùng máy để tự khởi động.
- Local outbox replay idempotent sau một khoảng control-plane mất kết nối.

## Production Result

- Deployed 2026-08-01 tại `https://ads.lushmedia.net`; Alembic `20260801_0006` ở `head`.
- Worker hiện hữu `Ads Browser VPS 82` được backfill host `82.197.71.6`, SSH user `root`, trạng thái `installed`.
- Hermes Agent `v0.19.1` đã cài; service giữ `disabled/inactive` cho tới khi worker nhận provider config hợp lệ, sau đó worker mới `enable --now`.
- Predeploy backup: `/opt/meta-ads-backups/20260801-125156` gồm source, env và PostgreSQL dump.
- Canonical public Git repo: `pearhoang/ads-facebook-automation`; production tracking `origin/main` và popup worker dùng repo này mặc định.
- DeepSeek preset dùng `https://api.deepseek.com` + `deepseek-v4-flash`; chờ raw API key để lưu encrypted và start Hermes.
