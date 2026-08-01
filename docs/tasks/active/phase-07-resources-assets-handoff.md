# Phase 07 Resources, Assets And Human Handoff

## Goal
- Hoàn thiện dữ liệu đầu vào cho Meta draft bằng registry tài nguyên, kho creative asset và phiên noVNC mở đúng URL cần người dùng xử lý.
- Cho phép test đầy đủ control plane trên ad account chưa có payment method; mọi browser mutation vẫn unpublished và dừng trước `Publish`.

## Scope
- Models/migration/API cho Meta resource và creative asset theo tenant/ad account.
- Campaign form chọn Page/Dataset/Form/App và media từ registry thay vì nhập tên rời rạc.
- Approved snapshot giữ exact label/external ID/asset digest; worker tải asset qua authenticated worker endpoint.
- Field plan mở rộng cho media, targeting cơ bản và schedule khi control khả dụng.
- Job `awaiting_user` có thể tạo browser session mở thẳng `current_url` của Meta draft.

## Constraints
- Không cần và không giả lập payment method.
- Không click `Đăng`/`Publish`; không tự đánh dấu resource là verified.
- Asset và resource phải tenant-scoped, ad-account-scoped; worker chỉ tải asset được tham chiếu bởi job của chính worker.
- Password/2FA vẫn chỉ nhập trực tiếp trong noVNC.

## Current State
- Schema/API/UI registry, asset streaming/digest, campaign snapshot, worker download/media handler, targeting cơ bản và noVNC handoff đã triển khai production.
- Production có Page thật đã xác minh và creative thật theo exact ad account; approved Awareness snapshot đã chạy E2E đến Review.
- Payment method vẫn chưa có và không thuộc Phase 7; draft builder không click `Đăng` và không có publish executor.

## Next Steps
- Chuyển sang phase tiếp theo cho reporting/KPI hoặc thiết kế payment/publish guardrail riêng; không gộp publish vào draft builder.
- Hai Meta draft E2E lịch sử `120250168499600033` và `120250168549870033` đã được owner xác nhận và xóa theo exact ID/name; draft đạt Review `120250169244880033` vẫn được giữ với `published=false`.

## Verification
- Local: `34 passed`, Python compile sạch.
- Production: Alembic `20260731_0004` ở `head`; resource/asset/objective APIs trả `200`; sáu objective có targeting và asset requirements.
- UI smoke mở thành công resource dialog, asset dialog và job detail có `Mở noVNC xử lý`; console `0` error/warning.
- Không tạo Meta resource/asset/session/job mới và không click `Publish` trong smoke.
- E2E job `e18ca3b5-aaa4-4ac7-9c2b-933701768990` đạt `review_ready`; artifact Review `f1d53039-d97e-4d85-98e9-f9dd79e62621`; `published=false`.

## Risks
- Meta file input và targeting DOM có thể lazy-render hoặc thay đổi; handler phải trả `not_available`/`failed`, không suy diễn thành công.
- Video lớn phải stream qua storage/download, không nạp toàn bộ vào RAM.
