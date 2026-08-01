# Phase 08 Reporting Và KPI

## Goal

- Thu thập dữ liệu hiệu quả quảng cáo bằng browser job read-only trên đúng Chrome profile của ad account.
- Lưu snapshot KPI bất biến để dashboard, báo cáo định kỳ và AI/Hermes dùng chung một nguồn dữ liệu.
- Hỗ trợ lịch báo cáo hằng ngày và gửi bản tóm tắt Telegram khi worker đã được cấu hình bot token.

## Scope

- Models/migration cho `report_schedules`, `report_jobs` và `report_snapshots`.
- User API cho manual collection, lịch hằng ngày, job history và snapshot history.
- Worker contract riêng cho report job; không gắn reporting vào campaign approval/execution job.
- Ads Manager DOM collector chỉ đọc table hiện có, không thay đổi campaign/budget và không click `Publish`.
- Trang `/reports` table-first, có ad account filter, KPI gần nhất, job history và schedule management.

## Safety

- Manual collection yêu cầu confirmation `THU THẬP KPI`.
- Scheduled collection chỉ chạy profile đã đăng nhập, không có browser session hoặc execution job đang giữ profile.
- Payload bắt buộc `mode=report_read_only`, `allow_ad_mutation=false`, `allow_publish=false`.
- `TELEGRAM_BOT_TOKEN` chỉ nằm trong worker environment; UI/database chỉ giữ `telegram_chat_id`.
- Thiếu bot token không làm mất snapshot: collection vẫn thành công, delivery được ghi `not_configured`.

## Verification

- Unit/integration test tenant isolation, scheduler idempotency, worker transitions và DOM parser.
- Alembic upgrade/check sạch trên production.
- Production smoke tạo một manual report job cho ad account thật, worker sync snapshot và không tạo/publish Meta entity.

## Current State

- Backend/API/UI, scheduler, worker DOM collector và Telegram adapter đã deploy production.
- Local regression: `38 passed`; Python compile và JavaScript syntax sạch.
- Production job `1dcdcabb-adeb-4359-8549-a93dee4af385` succeeded, tạo snapshot `8cf08819-28e1-495a-b4aa-eb4ff7146f79` cho kỳ 25/07–31/07/2026.
- Snapshot có `clicked=false`, `ad_mutated=false`, `published=false`; không có active session/job sau smoke.
- UI `/reports` console `0` error/warning; mojibake display name đã sửa exact row thành `Quản trị viên` UTF-8.
- Telegram token chưa cấu hình; chức năng gửi sẽ hoạt động sau khi thêm `TELEGRAM_BOT_TOKEN` vào worker env và restart riêng worker.
