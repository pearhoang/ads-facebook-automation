# Phase 05 Objective Adapters

Status: complete for surveyed default paths

## Goal

- Khảo sát khác biệt giữa sáu mục tiêu Meta Ads và đưa kết quả thành contract dùng chung cho form, preview và browser worker.

## Delivered

- Discovery scripts có exact-name/ID cleanup và không publish.
- Canonical objective catalog + authenticated API.
- Form campaign thay đổi conversion/performance/field theo objective.
- Draft job mang immutable `objective_adapter`; Traffic xử lý setup modal thủ công.
- Preview dùng warning/blocker theo objective và chỉ chấp nhận default path đã khảo sát.
- Resume draft chỉ theo exact campaign name.

## Production Result

- Đã khảo sát đủ sáu objective trên Meta production account bằng draft tạm và xóa sạch các draft discovery.
- Legitimate campaign `6982618414377` được bảo toàn; không click Publish.
- `ads.lushmedia.net` đã deploy Phase 5, API trả `200`, UI smoke đủ sáu objective và không tạo dữ liệu test.
- Web/worker active, PostgreSQL healthy, test suite `19 passed`.

## Next Step

- Phase 6 nên hoàn thiện field-filling adapter tại Ad Set/Ad cho từng default path, bắt đầu từ Sales hoặc Traffic với dữ liệu creative thật.
- Conversion location ngoài default path cần discovery + adapter riêng trước khi mở automation.

