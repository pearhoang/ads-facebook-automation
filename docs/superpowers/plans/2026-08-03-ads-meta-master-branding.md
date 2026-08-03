# Ads Meta Master Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đổi toàn bộ visible branding của control-plane sang `Ads Meta Master`, thêm icon/favicon riêng và rút gọn footer thành `Admin` mà không thay đổi runtime contract.

**Architecture:** Static SVG mới là canonical brand asset dùng đồng thời trong sidebar, login và favicon. Jinja templates chỉ đổi visible copy/asset reference; test source khóa contract branding và bảo vệ các identifier runtime `ads_lush_*` khỏi bị đổi nhầm.

**Tech Stack:** FastAPI, Jinja2 templates, static CSS/SVG, pytest, Playwright/local browser smoke.

## Global Constraints

- Domain `ads.lushmedia.net` và `hermes.ads.lushmedia.net` không đổi.
- Cookie, marker, provider ID, script/service name và remote path chứa `ads_lush` hoặc `ads-lush` không đổi.
- Brand name hiển thị là `Ads Meta Master`; subtitle là `Meta Ads Automation`.
- Footer sidebar chỉ hiển thị trạng thái, `Admin` và action `Đổi mật khẩu` ở nơi đã hỗ trợ action này.
- Icon là SVG riêng của sản phẩm, không sao chép logo Meta infinity hoặc Facebook `f`.
- Mọi template giữ UTF-8 và khai báo favicon mới.

---

### Task 1: Khóa branding contract bằng test

**Files:**
- Modify: `tests/test_auth_flow.py`

**Interfaces:**
- Consumes: các Jinja template trong `backend/app/templates/` và static asset path `/static/ads-meta-master.svg`.
- Produces: integration test `test_ads_meta_master_branding_is_consistent_across_rendered_pages()` cho visible brand, favicon, static asset và footer mới.

- [x] **Step 1: Viết failing integration test cho brand, favicon và footer**

Thêm test sau vào `tests/test_auth_flow.py`; test gọi route thật, dùng tenant fixture tên `Lush Media` để chứng minh tên cũ không còn rò vào UI:

```python
def test_ads_meta_master_branding_is_consistent_across_rendered_pages():
    with build_production_client() as client:
        provision(client)

        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert "Ads Meta Master" in login_page.text
        assert "Meta Ads Automation" in login_page.text
        assert 'rel="icon" type="image/svg+xml" href="/static/ads-meta-master.svg"' in login_page.text
        assert "Ads Lush" not in login_page.text
        assert "Automation workspace" not in login_page.text

        logged_in = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "admin", "password": PASSWORD},
        )
        assert logged_in.status_code == 200

        for path in ("/", "/campaigns", "/reports", "/bot-nodes", "/hermes-agents"):
            page = client.get(path)
            assert page.status_code == 200
            assert "Ads Meta Master" in page.text, path
            assert "Meta Ads Automation" in page.text, path
            assert '<strong>Admin</strong>' in page.text, path
            assert 'rel="icon" type="image/svg+xml" href="/static/ads-meta-master.svg"' in page.text, path
            assert "Ads Lush" not in page.text, path
            assert "Automation workspace" not in page.text, path
            assert "Lush Media" not in page.text, path

        asset = client.get("/static/ads-meta-master.svg")
        assert asset.status_code == 200
        assert asset.headers["content-type"].startswith("image/svg+xml")
        assert 'viewBox="0 0 32 32"' in asset.text
        assert "<script" not in asset.text
        assert "xlink:href" not in asset.text
        assert "data:" not in asset.text
```

- [x] **Step 2: Cập nhật assertion auth theo visible brand mới**

Trong `test_login_cookie_csrf_logout_and_workspace_guard()`, thay assertion `"Lush Media" in workspace.text` bằng các assertion:

```python
assert "Ads Meta Master" in workspace.text
assert "Meta Ads Automation" in workspace.text
assert "<strong>Admin</strong>" in workspace.text
assert "Lush Media" not in workspace.text
```

Giữ nguyên mọi assertion cookie `ads_lush_session` và `ads_lush_csrf`.

- [x] **Step 3: Chạy test để xác nhận đang fail đúng lý do**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_auth_flow.py::test_ads_meta_master_branding_is_consistent_across_rendered_pages tests/test_auth_flow.py::test_login_cookie_csrf_logout_and_workspace_guard -q`

Expected: FAIL vì template chưa có `Ads Meta Master`/favicon và vẫn render `Lush Media`.

### Task 2: Triển khai static brand asset và visible copy

**Files:**
- Create: `backend/app/static/ads-meta-master.svg`
- Modify: `backend/app/static/workspace.css`
- Modify: `backend/app/static/auth.css`
- Modify: `backend/app/templates/login.html`
- Modify: `backend/app/templates/workspace.html`
- Modify: `backend/app/templates/campaigns.html`
- Modify: `backend/app/templates/reports.html`
- Modify: `backend/app/templates/bot_nodes.html`
- Modify: `backend/app/templates/hermes_agents.html`
- Modify: `backend/app/templates/ai_copilot.html`

**Interfaces:**
- Consumes: test contract từ Task 1.
- Produces: static asset `/static/ads-meta-master.svg` và markup brand đồng nhất trên mọi control-plane template.

- [x] **Step 1: Tạo SVG brand mark tối giản**

Tạo `backend/app/static/ads-meta-master.svg` với nội dung:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Ads Meta Master">
  <rect width="32" height="32" rx="7" fill="#1877F2"/>
  <path d="M7 23V11.2c0-1.8 2.2-2.6 3.4-1.2l5.6 6.4 5.6-6.4c1.2-1.4 3.4-.6 3.4 1.2V23" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

Đây là monogram `M` riêng của sản phẩm, không chứa text, script, external URL, gradient hoặc raster data.

- [x] **Step 2: Cập nhật CSS brand mark**

Thay rule `.brand-mark` bằng:

```css
.brand-mark { display: block; width: 32px; height: 32px; flex: 0 0 32px; }
```

Bỏ nền cam và rule typography chỉ dành cho chữ `A`. Không đổi `--accent` của action button trong task này.

- [x] **Step 3: Cập nhật brand block, title và favicon trên mọi template**

Mỗi template thêm:

```html
<link rel="icon" type="image/svg+xml" href="/static/ads-meta-master.svg">
```

Brand block dùng:

```html
<img class="brand-mark" src="/static/ads-meta-master.svg" alt="">
<span><strong>Ads Meta Master</strong><small>Meta Ads Automation</small></span>
```

Đổi `aria-label` và `<title>` sang `Ads Meta Master`. Đổi câu `Chỉ lưu bản nháp trong Ads Lush.` thành `Chỉ lưu bản nháp trong Ads Meta Master.`.

- [x] **Step 4: Rút gọn footer sidebar**

Trên năm template chính, thay tenant/role/module context bằng `<strong>Admin</strong>` và giữ nguyên button `Đổi mật khẩu`. Trên legacy `ai_copilot.html`, chỉ giữ status dot cùng `<strong>Admin</strong>` vì trang này không render password dialog.

- [x] **Step 5: Chạy test branding và auth**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_auth_flow.py tests/test_utf8_ui.py -q`

Expected: PASS.

- [x] **Step 6: Quét visible copy cũ và runtime identifier**

Run: `rg -n "Ads Lush|Automation workspace|principal\.tenant_name" backend/app/templates`

Expected: không có kết quả.

`principal.role` vẫn được giữ trong `data-role` của Campaigns/Reports vì đây là authorization context cho frontend, không phải footer copy.

Run: `rg -n "ads_lush_session|ads_lush_csrf" backend/app/config.py tests/test_auth_flow.py`

Expected: runtime cookie identifiers vẫn còn nguyên.

### Task 3: Đồng bộ project memory và xác minh local

**Files:**
- Modify: `docs/UI_SYSTEM.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-08-03-ads-meta-master-branding.md`

**Interfaces:**
- Consumes: UI implementation từ Task 2.
- Produces: project memory hiện hành, verification evidence và local preview ở `http://127.0.0.1:8010`.

- [x] **Step 1: Cập nhật UI system canonical**

Đổi visual direction sang nhận diện `Ads Meta Master`, ghi canonical subtitle `Meta Ads Automation`, custom SVG dùng chung cho brand/favicon và footer `Admin`. Xóa quy tắc footer `Lush Media`; giữ nguyên domain/deployment facts ở module infra.

- [x] **Step 2: Append changelog ngắn**

Thêm entry ngày `2026-08-03` mô tả visible branding, favicon và footer; nêu rõ không đổi domain/runtime identifiers.

- [x] **Step 3: Chạy verification đầy đủ**

Run: `.\.venv\Scripts\python.exe -m pytest`

Expected: toàn bộ test PASS.

Run: `.\.venv\Scripts\python.exe -m compileall -q backend workers`

Expected: exit code 0 và không có syntax error.

- [x] **Step 4: Bật local preview**

Khởi động Uvicorn bằng local SQLite riêng trên port 8010, không dùng production database hoặc service:

```powershell
$env:DATABASE_URL='sqlite:///./data/ads-meta-master-preview.db'
$env:APP_ENV='development'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

Expected: `http://127.0.0.1:8010/health` trả `200` và local login/workspace render từ source vừa sửa.

- [x] **Step 5: Browser smoke UI**

Mở local preview và kiểm tra desktop:

- brand block có icon mới, `Ads Meta Master`, `Meta Ads Automation`;
- footer chỉ có `Admin` và `Đổi mật khẩu` sau login;
- tab có title mới và favicon SVG;
- không có mojibake hoặc layout regression rõ ràng.

Lưu screenshot local vào `output/playwright/ads-meta-master-local.png` nếu công cụ browser hỗ trợ.

- [x] **Step 6: Commit implementation nhưng không push/deploy**

Run:

```powershell
git add -- backend/app/static/ads-meta-master.svg backend/app/static/workspace.css backend/app/static/auth.css backend/app/templates tests/test_auth_flow.py docs/UI_SYSTEM.md docs/CHANGELOG.md docs/superpowers/plans/2026-08-03-ads-meta-master-branding.md
git commit -m "Refresh Ads Meta Master branding"
```

Expected: commit local thành công; không chạy `git push` và không thao tác production.
