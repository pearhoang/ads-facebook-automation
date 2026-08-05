# Resource And Asset Registry

## Responsibility
- Quản lý exact metadata cho Page, Instagram account, Dataset/Pixel, Instant Form và App theo tenant/ad account.
- Lưu creative image/video được ingest từ Telegram/Hermes trên control plane với SHA-256 và cung cấp download chỉ cho worker/job hợp lệ.
- Không tự khám phá hoặc tự xác minh resource trên Meta; trạng thái verified cần hành động rõ của user/admin.

## Entry Points
- API route: `backend/app/api/campaigns.py`, worker download tại `backend/app/api/worker.py`.
- UI page: `/ad-accounts` chỉ quản lý Meta resource; creative asset registry là backend contract, không phải thư viện upload thủ công cho user.
- Worker consumer: `ExecutionJobSupervisor` tải asset trước khi chạy `MetaDraftBuildRuntime`.

## Key Files
- `backend/app/models.py`
- `backend/app/services/resources.py`
- `backend/app/static/ad_accounts.js`
- `workers/agent/control_plane.py`
- `workers/agent/execution.py`

## Depends On
- Authenticated tenant/CSRF boundary, ad account ownership, execution job worker ownership và persistent runtime storage.

## Used By
- Agent orchestration snapshot, Meta draft builder và noVNC challenge recovery flow.

## Invariants
- Resource/asset không thể được dùng chéo tenant hoặc ad account.
- Resource có thể xóa khỏi registry khi không có execution/automation active cùng ad account; snapshot lịch sử không phụ thuộc registry hiện hành.
- File lưu bằng generated path, không dùng trực tiếp user filename; download phải kiểm tra job payload tham chiếu đúng asset.
- Snapshot giữ exact label/external ID/digest; worker xác minh digest sau download.
- Không có endpoint publish hoặc payment mutation.

## Known Pitfalls
- User filename và MIME header không đủ tin cậy; cần filename normalization, allowlist MIME và size limit.
- Resource label giống nhau có thể tồn tại ở ad account khác; mọi lookup phải kèm tenant/ad account.

## Related Decisions
- `DEC-015`
- `DEC-016`
- `DEC-029`

## Production Evidence

- Alembic revision `20260731_0004` tạo `meta_resources`, `creative_assets` và `browser_sessions.launch_url`.
- Production API smoke: registry resource/asset rỗng trả `200`; objective catalog đủ sáu adapter và Awareness có Page, country, asset, primary text là required.
- UI smoke mở đúng hai registry dialog và noVNC handoff action; không tạo dữ liệu giả trên ad account test.
- Full suite: `27 passed`; có coverage cho tenant/ad-account ownership, exact verification, MIME spoof, duplicate digest và worker download authorization.
- Page production `113903128387475` (`Stable Diffusion AI Chia Sẻ Thủ Thuật, Kiến Thức, Tin Tức, Tài Nguyên`) ở trạng thái `verified` trên ad account `2321387601366948`.
- Asset `stable-diffusion-draft-creative.png`, `2,439,367` bytes, SHA-256 `85c09c701a859a075bb14247e56d9e5fb88a742c368a82d78ce62b7bfe739d6e`, trạng thái `ready`; E2E worker đã upload asset này vào Meta draft.
