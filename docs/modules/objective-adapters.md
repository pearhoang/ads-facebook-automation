# Objective Adapters

## Responsibility

- Giữ một catalog canonical cho sáu mục tiêu Meta Ads đã khảo sát trên giao diện production.
- Mô tả default path, setup mode, conversion location, performance goal và field cần thiết để backend, UI và worker dùng cùng một contract.
- Chỉ tự động hóa default path đã xác minh; path khác phải dừng ở preview cho đến khi có adapter riêng.

## Canonical Source

- Catalog: `backend/app/services/objective_specs.py`.
- Authenticated API: `GET /api/objective-specs`.
- Draft job snapshot: `payload_json.objective_adapter`.
- Worker fallback cho job Phase 4 cũ: `MetaDraftBuildRuntime.LEGACY_ADAPTERS`.

## Surveyed Default Paths

| Objective | Setup | Default path | Performance goal | Objective-specific input |
|---|---|---|---|---|
| `awareness` | direct | Mức độ nhận biết | Tối đa hóa số người tiếp cận quảng cáo | Page, primary text |
| `traffic` | manual | Website | Tăng tối đa số lượt xem trang đích | Page, primary text, destination URL |
| `engagement` | direct | Đích đến của tin nhắn | Tối đa hóa số cuộc trò chuyện | Page, messaging destination, primary text |
| `leads` | direct | Mẫu phản hồi tức thì | Tối đa hóa số khách hàng tiềm năng | Page, Instant Form, primary text |
| `app_promotion` | direct | Cửa hàng ứng dụng | Tối đa hóa số lượt cài đặt ứng dụng | Page, app name, primary text |
| `sales` | direct | Website | Tối đa hóa số lượt chuyển đổi | Page, primary text, destination URL; dataset/event là optional |

Traffic có modal trung gian và worker phải chọn `Chiến dịch lưu lượng truy cập thủ công` trước khi vào Campaign editor.

## Invariants

- UI không tự hard-code danh sách objective; mọi option và default label lấy từ API catalog.
- Preview tạo blocker nếu objective chưa có adapter hoặc conversion location khác default path.
- Field thiếu của đúng objective là warning/`awaiting_user`; destination URL không còn là yêu cầu chung cho mọi objective.
- Worker chỉ resume campaign có tên trùng chính xác; không dùng tên mặc định chung của Meta để đoán draft.
- Không có objective adapter nào được phép click `Đăng`/`Publish`.
- `field_actions` là declarative stage plan canonical; worker chỉ dùng handler đã đăng ký và exact value từ approved snapshot.
- Mọi action ghi lại `field_results`; field không hiện hoặc không xác nhận được giá trị không được coi là hoàn tất.

## Production Evidence

- Khảo sát đủ sáu objective bằng các discovery campaign unpublished trên ad account test ngày 2026-07-31.
- Mỗi discovery campaign đã được xóa ở Campaign level theo exact ID/name; campaign hợp lệ `6982618414377` vẫn còn.
- Production UI smoke: API objective specs `200`, đủ sáu option và đúng conditional field; không lưu campaign khi kiểm tra.
- Artifact khảo sát local: `output/playwright/objective-discovery/`.
- Phase 6 discovery Sales `6982633575177`: campaign budget và destination URL được áp dụng; default Sales surface được xác minh; Page giả bị từ chối exact-match; draft đã cleanup và không publish.

## Verification

- `tests/test_objective_specs.py` kiểm tra đủ sáu adapter, Traffic manual setup và warning theo objective.
- `tests/test_execution_preflight_flow.py` kiểm tra draft job chứa adapter snapshot.
- `tests/test_meta_fields.py` kiểm tra stage planner, required/optional field và snapshot value mapping.
- Full suite Phase 7: `27 passed`; common plan thêm country, age range, placements và creative asset.
