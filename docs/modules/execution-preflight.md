# Execution Preflight

## Responsibility

- Chuyển campaign đã approve thành preflight job read-only cho worker sở hữu Chrome profile.
- Kiểm tra Facebook login, Ads Manager page và đúng ad account trước khi xây publish executor.
- Thu screenshot artifact và kết quả kỹ thuật theo tenant.

## Entry Points

- Models: `ExecutionJob`, `ExecutionArtifact` trong `backend/app/models.py`.
- Service: `backend/app/services/execution_jobs.py`.
- User API: `backend/app/api/execution.py`.
- Worker API: execution routes trong `backend/app/api/worker.py`.
- Runtime: `workers/agent/execution.py`.
- Migration: `20260731_0003_execution_preflight.py`.

## Flow

1. Campaign phải ở `approved` và version khớp approved snapshot.
2. UI tải execution preview và hiển thị blockers.
3. Owner/admin nhập đúng `CHẠY PREFLIGHT`.
4. Backend tạo job `queued` với safety payload read-only.
5. Worker claim theo lease, chạy headless Chromium bằng persistent profile.
6. CDP chỉ đọc URL/title/body state và chụp screenshot; không click.
7. Worker sync `succeeded`, `awaiting_user` hoặc `failed` và upload artifact.

## State Machine

- `queued → claimed → running → succeeded`.
- `claimed|running → awaiting_user|failed`.
- `awaiting_user|failed → queued` qua explicit retry.
- Lease hết hạn đưa `claimed|running` về `queued`; preflight là read-only nên retry an toàn.

## Invariants

- Không tạo job nếu campaign chưa approve, worker stale, profile chưa authenticated hoặc browser session đang active.
- Một campaign chỉ có một active preflight job.
- Worker/profile ownership lấy từ ad account → Facebook account → assigned worker.
- Payload luôn có `allow_click=false` và `allow_publish=false`.
- Không có endpoint publish, budget mutation hoặc Ads Manager click trong Phase 3.
- Artifact path do backend sinh, giới hạn size/type và download bắt buộc đúng tenant.

## Verification

- `tests/test_execution_preflight_flow.py` kiểm tra role, confirmation, state, tenant, worker sync và artifact.
- `tests/test_worker_execution_supervisor.py` kiểm tra happy path và profile-busy guard.
- Regression suite sau Phase 4: `15 passed`; Alembic `20260731_0003 (head)` và drift sạch.

## Related Decisions

- `DEC-003`
- `DEC-011`
- `DEC-012`
- `DEC-013`
