# Campaign Draft And Approval

## Responsibility

- Quản lý ad account nội bộ, campaign draft, approval request và audit event theo tenant.
- Cung cấp approval gate trước mọi phase có khả năng ghi dữ liệu lên Meta.
- Approval vẫn không tự chạy executor; Phase 3 chỉ thêm preflight read-only và không có Meta mutation.

## Entry Points

- Models: `backend/app/models.py` (`AdAccount`, `CampaignDraft`, `ApprovalRequest`, `AuditEvent`).
- Service/state machine: `backend/app/services/campaigns.py`.
- API: `backend/app/api/campaigns.py`.
- UI: `/campaigns`, `templates/campaigns.html`, `static/campaigns.js`.
- Migration: `20260731_0002_campaign_approval.py`.

## State Machine

- `draft → pending_approval → approved`.
- `pending_approval → rejected → draft` sau khi có revision.
- Campaign `pending_approval` hoặc `approved` không thể chỉnh sửa.
- Mỗi campaign chỉ có tối đa một approval request `pending`.
- Snapshot trong approval request cố định version, budget, schedule, targeting và creative tại lúc submit.

## Authorization And Safety

- Tenant lấy từ authenticated principal; mọi query đều lọc `tenant_id`.
- Mutation yêu cầu CSRF.
- Chỉ role `owner` hoặc `admin` được approve/reject.
- Reject bắt buộc có lý do.
- `approved` chỉ là duyệt nội bộ; không đồng nghĩa đã publish lên Meta.
- Preflight phải có explicit confirmation riêng sau approval.
- Mọi create/update/submit/approve/reject đều tạo `AuditEvent`.
- Ad account hỗ trợ `PATCH /api/ad-accounts/{id}`; label luôn được đổi, còn Meta ID/currency/timezone bị khóa khi đã có campaign/resource/asset phụ thuộc để tránh đổi identity âm thầm.

## Money Contract

- Database/API giữ `daily_budget_minor` dạng integer.
- Currency lấy từ ad account, không cho campaign tự đổi currency.
- UI áp dụng exponent 0 cho `VND`, `JPY`, `KRW`; các currency còn lại dùng 2 chữ số thập phân.

## Verification

- `tests/test_campaign_approval_flow.py` kiểm tra state transitions, tenant isolation, CSRF, role, immutable pending draft và audit.
- `alembic check` phải không phát hiện drift.
- Kiểm tra route/API không tồn tại action `publish` trong Phase 2.
- Production đã đổi label account `2321387601366948` thành `Lê Hoàng` qua chính PATCH contract; DB giữ đúng UTF-8.

## Related Decisions

- `DEC-005`
- `DEC-011`
