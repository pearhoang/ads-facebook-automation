# Meta Ads Copilot

SaaS control plane và outbound browser worker cho Meta Ads automation.

Repository: `https://github.com/pearhoang/ads-facebook-automation`

## Phase hiện tại

Phase 01 đang xây Account Session vertical slice:

```text
Facebook account
→ worker assignment
→ browser session request
→ worker poll/sync
→ noVNC login/2FA
→ confirm/close
```

Runtime noVNC thật, outbound worker, HTTP/WebSocket proxy và UI Account Session đã hoạt động trên VPS test.

## Test deployment

- URL chuẩn: `https://ads.lushmedia.net`
- IP `http://82.197.71.6` redirect sang URL HTTPS chuẩn.
- Đăng nhập bằng application account; không còn dùng Caddy Basic Auth.
- Owner credential được lưu ngoài repo và bàn giao riêng.
- Services: `meta-ads-copilot-web.service`, `meta-ads-copilot-worker.service`.
- Bot VPS mới clone branch `main` từ repository mặc định; URL có thể sửa trong popup cài worker.
- Hermes hỗ trợ OpenAI-compatible provider; preset mặc định hiển thị DeepSeek V4 Flash 0731 và dùng API model ID `deepseek-v4-flash`.
- Database: PostgreSQL 17.10, schema quản lý bằng Alembic.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

OpenAPI: `http://127.0.0.1:8000/docs`

Migration:

```powershell
$env:DATABASE_URL = "sqlite:///./data/app.db"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall -q backend workers
```

## Safety status

- Production dùng opaque server-side session, Argon2 password hash, Secure/HttpOnly cookie và CSRF protection.
- Tenant được lấy từ membership của phiên đăng nhập, không nhận từ client header.
- noVNC/websockify bind localhost và chỉ truy cập qua backend proxy.
- Local/test có thể dùng SQLite; production dùng PostgreSQL và không chạy `create_all`.
- Không dùng build hiện tại để chạy campaign có ngân sách thật.
