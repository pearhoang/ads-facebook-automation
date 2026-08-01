# Reporting Và KPI

## Responsibility

- Backend quản lý lịch, report job, worker lease và snapshot KPI bất biến theo tenant/ad account.
- Worker mở đúng persistent Chrome profile, đọc Campaigns table trong Ads Manager và sync kết quả về backend.
- Telegram delivery là phần deterministic của report job; AI narrative/suggestion vẫn thuộc Hermes ở phase sau.

## Entry Points

- User API/UI: `backend/app/api/reports.py`, `backend/app/services/reporting.py`, `/reports`.
- Worker API: `/api/workers/{worker_id}/report-jobs/poll|sync`.
- Browser runtime: `workers/agent/reporting.py`.
- Schema: `report_schedules`, `report_jobs`, `report_snapshots`; migration `20260801_0005`.

## Invariants

- Manual run cần confirmation `THU THẬP KPI`.
- Job payload phải có `mode=report_read_only`, `allow_filter_click=false`, `allow_ad_mutation=false`, `allow_publish=false`.
- Report range chỉ dùng ngày đã hoàn tất và kết thúc vào hôm qua theo timezone của ad account.
- Snapshot chỉ tạo khi worker trả safety proof `ad_mutated=false` và `published=false`.
- Một ad account tối đa một report job `queued|claimed|running`; browser session và execution job cùng profile luôn loại trừ report job.
- `TELEGRAM_BOT_TOKEN` chỉ ở worker env; database/UI chỉ giữ chat ID. Thiếu token không làm mất snapshot.

## Current Production State

- Phase 8 đã deploy tại `https://ads.lushmedia.net/reports`.
- Alembic `20260801_0005` ở `head`; web/worker active.
- Manual smoke job `1dcdcabb-adeb-4359-8549-a93dee4af385` tạo snapshot thành công cho ad account `2321387601366948`; dữ liệu hiện bằng 0 vì chưa chạy quảng cáo.
- Telegram token chưa cấu hình nên production hiện chỉ lưu báo cáo trên web.

## Risks

- Ads Manager grid có thể đổi role/header hoặc lazy-render; parser chỉ công nhận các column đã nhìn thấy và giữ header/raw mapping trong result.
- Account chưa setup hoặc chưa có delivery có thể trả bảng rỗng; đây là snapshot hợp lệ với KPI bằng 0, không phải bằng chứng campaign đang chạy.
- Scheduled Telegram delivery cần token/chat ID đúng; lỗi delivery phải hiện riêng, không đổi snapshot collection thành thất bại.

## Related Decisions

- `DEC-001`, `DEC-002`, `DEC-003`, `DEC-018`.

