# Meta Draft Builder

## Responsibility

- Chuyển approved campaign snapshot thành unpublished Meta Campaign/Ad Set/Ad trên đúng persistent Chrome profile.
- Tự động hóa happy path bằng deterministic CDP state machine, lưu checkpoint và dừng an toàn khi thiếu dữ liệu hoặc UI drift.
- Không click `Đăng`/`Publish`.

## Entry Points

- Backend service/preview: `backend/app/services/execution_jobs.py`.
- User API: `backend/app/api/execution.py`.
- Worker control-plane client: `workers/agent/control_plane.py`.
- Runtime/state machine: `workers/agent/execution.py`.
- User không review checkpoint trong control-plane; worker gửi progress/artifact cần thiết qua Telegram hoặc Hermes Dashboard. `/campaigns` chỉ giữ reporting; artifact vẫn lưu internal để recovery/audit.

## Flow

1. Campaign ở `approved`, version không đổi và có preflight thành công cùng version.
2. UI hiển thị blockers/warnings và yêu cầu confirmation `TẠO DRAFT META`.
3. Backend enqueue `draft_build` với safety contract draft-only.
4. Worker mở đúng Chrome profile và Ads Manager của ad account.
5. Worker chỉ resume pending draft trùng chính xác campaign name; nếu không thì tạo campaign mới và chọn objective theo adapter snapshot.
6. Traffic chọn nhánh `Chiến dịch lưu lượng truy cập thủ công`; objective khác đi thẳng vào editor theo default path đã khảo sát.
7. Worker lập declarative field plan, tua/cuộn Meta editor để tìm control lazy-rendered và điền/xác minh từng field theo thứ tự Campaign, Ad Set, Ad.
8. Creative image/video dùng Meta content wizard và native file chooser qua `Page.fileChooserOpened`/`DOM.setFileInputFiles`; wizard phải đóng bằng `Tiếp`/`Xong` trước Review.
9. Mỗi field trả kết quả có stage/handler/status/detail; worker upload screenshot ở mỗi checkpoint.
10. Khi đủ dữ liệu, worker dừng tại Review trước publish; khi thiếu field/UI drift, trả `awaiting_user`/`failed`.
11. Worker tải creative asset được job tham chiếu, xác minh SHA-256, điền targeting cơ bản và file chooser; user có thể mở noVNC tại exact `current_url` để xử lý phần Meta yêu cầu thủ công.

## Invariants

- Một campaign chỉ có một active `draft_build` job.
- Retry không tạo thêm draft nếu pending draft trùng chính xác campaign đã tồn tại; không resume tên Meta mặc định chung.
- Danh sách campaign phải qua stabilization window trước exact-name resume; bảng Meta render toolbar/result count sớm hơn row.
- Mỗi job giữ `objective_adapter` immutable từ approved snapshot; path ngoài adapter bị block trước enqueue.
- Payload luôn có `mode=draft_only`, `allow_click=true`, `allow_publish=false`, `stop_before=publish`.
- Không có code path click nút `Đăng`/`Publish`.
- Artifact thuộc tenant và có các kind `campaign_step`, `adset_step`, `ad_step`, `review_step`, `failure`.
- Missing field được tính theo objective adapter; destination URL chỉ bắt buộc cho Traffic/Sales.
- Không dùng việc đã điều hướng qua stage làm bằng chứng field thành công; chỉ `applied`, `already_set` hoặc `verified` mới là kết quả xác nhận.

## Production Evidence

- E2E Awareness job `e18ca3b5-aaa4-4ac7-9c2b-933701768990` thành công ngay attempt 1: `review_ready`, checkpoints `campaign/adset/ad`, không blocker và `safety.published=false`.
- Exact Meta IDs được resume: campaign `120250169244880033`, ad set `120250169244900033`, ad `120250169244890033`; artifact Review `f1d53039-d97e-4d85-98e9-f9dd79e62621` không còn modal và hiển thị nút `Đăng` chưa click.
- Page/country `already_set`, budget Ad Set `applied`, media upload `applied`, primary text `applied`, content wizard `applied`.

- Job `6dd84a54-19f6-4574-adc6-2c6c248fb4e9`, attempt 4, kết thúc `awaiting_user`, phase `ad`.
- Meta IDs mới: campaign `6982618414377`, ad set `6982618414777`, ad `6982618414577`.
- Checkpoints: `campaign`, `adset`, `ad`; review screenshot được lưu; `safety.published=false`.
- Draft cũ đã được xóa có guard theo đúng tên; smoke tạo draft mới từ đầu với objective Sales.
- Các trường còn thiếu trong snapshot test: Page Facebook, primary text, destination URL.
- Phase 6 discovery Sales `6982633575177` đã đi đủ Campaign/Ad Set/Ad: budget `applied`, Sales defaults `verified`, URL `applied`, CTA `already_set`; dừng an toàn do Page giả và creative control chưa khả dụng.
- Discovery draft được xóa bằng exact ID/name; `safety.published=false`.

## Verification

- `tests/test_execution_preflight_flow.py` kiểm tra prerequisite preflight, confirmation, safety payload và tenant contract.
- `tests/test_worker_execution_supervisor.py` kiểm tra routing draft builder, checkpoint upload và `published=false`.
- Phase 5 survey đủ sáu objective; discovery drafts đã xóa exact campaign ID/name và không publish.
- Full suite sau E2E: `34 passed`; Python compile sạch.

## Related Decisions

- `DEC-003`
- `DEC-011`
- `DEC-012`
- `DEC-013`
- `DEC-014`
- `DEC-015`
