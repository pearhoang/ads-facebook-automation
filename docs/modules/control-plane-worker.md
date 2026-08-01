# Control Plane And Worker

## Responsibility

- Backend quản lý tenant, opaque user sessions, workers, jobs, approvals và audit.
- Worker poll assignment, sở hữu browser runtime và sync kết quả về backend.

## Planned Entry Points

- Backend: `backend.app.main:app`
- Worker: `workers.agent.main`
- Worker API: register, heartbeat, session poll và session sync.

## Depends On

- PostgreSQL 17 và Alembic schema revision ở `head`.
- Worker shared-secret hoặc signed worker credential.
- Linux browser runtime cho real noVNC integration.

## Invariants

- Worker outbound-only.
- API route là thin adapter; state transition nằm trong service/store layer.
- Poll/sync phải idempotent và chịu được retry.
- Worker mất heartbeat không tự động đồng nghĩa Chrome profile bị mất.
- User API lấy tenant từ authenticated membership; worker API tiếp tục dùng credential riêng.
- Worker không đổi database contract trong lần SQLite → PostgreSQL cutover vì vẫn chỉ gọi HTTP API.

## Known Pitfalls

- Không copy monolithic `store.py` từ app cũ sang nguyên xi.
- Không public worker debug/noVNC ports trực tiếp.
- Tránh để job lease hết hạn trong khi browser vẫn đang chờ user 2FA.

## Related Decisions

- `DEC-001`
- `DEC-004`
- `DEC-006`
