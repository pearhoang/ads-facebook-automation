# Phase 04 Meta Draft Builder

Status: implementation complete, production workflow awaiting full creative input

## Goal

- Hoàn thiện vertical slice `Approved Campaign → Draft Preview → Explicit Confirm → Meta Campaign/Ad Set/Ad Draft → Checkpoints → Stop Before Publish`.

## Delivered

- Draft-specific preview, blockers/warnings, confirmation và retry.
- Structured campaign spec cho Page, targeting cơ bản, placements và creative fields.
- Deterministic browser state machine có create/resume và checkpoint artifacts.
- UI job detail cho phase, blocker, current URL và artifact.
- Production deployment không cần migration mới; tiếp tục dùng JSON snapshot/payload/result hiện có.

## Production Result

- Draft cũ đã xóa và một draft Sales mới đã được tạo từ đầu.
- Worker đổi tên campaign/ad set/ad theo approved snapshot và đi đến bước Ad.
- Job `6dd84a54-19f6-4574-adc6-2c6c248fb4e9` ở `awaiting_user`, attempt 4, phase `ad`.
- Meta draft có đủ 3 entity ID; 4 screenshot checkpoint được lưu.
- `safety.published=false`; nút `Đăng` vẫn nguyên và chưa được click.
- Final verified PostgreSQL dump: `/opt/meta-ads-copilot-runtime/postgres-backups/meta-ads-phase4-final-20260731-160702.dump`.

## User Input Needed For Full Review

- Chọn Page Facebook.
- Nhập primary text.
- Nhập destination URL.
- Có thể bổ sung headline/CTA nếu muốn thay default.

## Next Step

- Cập nhật approved campaign snapshot bằng các field trên, duyệt version mới và retry draft builder để đi đến Review.
- Thiết kế publish approval/action ở phase riêng; không mở publish trong Phase 4.
