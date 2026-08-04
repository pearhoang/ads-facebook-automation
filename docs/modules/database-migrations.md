# Database And Migrations

## Responsibility

- PostgreSQL là production source of truth cho control-plane state.
- Alembic là canonical schema manager; ORM metadata là input để kiểm tra drift.
- SQLite chỉ dùng cho local/test và giữ làm rollback snapshot của lần cutover đầu tiên.

## Entry Points

- `alembic.ini`, `migrations/env.py`, `migrations/versions/*`.
- `scripts/migrate_sqlite_to_postgres.py`: one-time transactional row copy.
- `infra/docker-compose.postgres.yml`: dedicated PostgreSQL runtime.

## Runtime

- Image: `postgres:17.10-alpine3.24`.
- Container: `meta-ads-postgres`.
- Host connection: `127.0.0.1:55432`; không public ra Internet.
- Database/user: `meta_ads_copilot` / `meta_ads_owner`.
- Data: `/opt/meta-ads-copilot-runtime/postgres-data`.
- Dumps: `/opt/meta-ads-copilot-runtime/postgres-backups`.
- Password: `/etc/meta-ads-copilot/postgres-password`, mode `0600`.

## Invariants

- Production startup không gọi `Base.metadata.create_all()`.
- Deploy schema bằng `alembic upgrade head` trước khi restart app dùng model mới.
- Chạy `alembic check` để phát hiện ORM/schema drift.
- Migration data phải chạy khi web đã dừng và không có active browser session.
- Worker không `Requires` web service; khi control-plane tạm dừng, worker giữ local state/outbox và reconnect sau.
- Không xóa SQLite snapshot hoặc PostgreSQL dump cho tới khi qua thời gian rollback đã thống nhất.

## Verification

- `alembic current` phải khớp revision mới nhất; Phase 12 dùng `20260804_0011 (head)`.
- `alembic check` phải trả `No new upgrade operations detected.`
- Auth/account counts phải khớp snapshot; active browser session bằng `0` sau smoke test.
- noVNC phải tải HTML và WebSocket nhận `RFB 003.008`.

## Related Decisions

- `DEC-010`
