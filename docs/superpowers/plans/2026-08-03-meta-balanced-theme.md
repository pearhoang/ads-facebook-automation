# Meta Balanced Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển tone UI sang blue–indigo–green, giữ red cho danger và giữ nguyên sidebar dark neutral hiện tại.

**Architecture:** `workspace.css` tiếp tục là canonical token layer cho toàn bộ Jinja UI. `auth.css` và `copilot.css` tái sử dụng token/cool surface thay cho warm gray trực tiếp; integration test gọi static route thật để khóa palette được phục vụ cho browser.

**Tech Stack:** FastAPI StaticFiles, CSS custom properties, Jinja UI, pytest, local in-app browser smoke.

## Global Constraints

- Primary blue là `#1877F2`; hover là `#166FE5`.
- Attention/safety indigo là `#4F46E5`; success green là `#16865F`.
- Danger red `#B83A3A` được giữ cho error, blocker và destructive action.
- Sidebar `#242321` và active navigation `#3A3733` không đổi.
- Không đổi layout, HTML copy, JavaScript behavior, API, database, route, worker contract hoặc deployment config.
- Loại bỏ mọi orange/amber literal đã liệt kê trong design spec khỏi product stylesheet.

---

### Task 1: Khóa palette contract bằng integration test

**Files:**
- Modify: `tests/test_auth_flow.py`

**Interfaces:**
- Consumes: static route `/static/workspace.css` từ FastAPI app thật.
- Produces: test `test_meta_balanced_theme_css_contract_is_served()` khóa canonical palette, retired colors và sidebar exception.

- [x] **Step 1: Viết failing integration test**

Thêm test sau vào `tests/test_auth_flow.py`:

```python
def test_meta_balanced_theme_css_contract_is_served():
    with build_production_client() as client:
        response = client.get("/static/workspace.css")
        assert response.status_code == 200
        css = response.text.lower()

        for token in (
            "--background: #f3f6fb;",
            "--surface-subtle: #f7f9fc;",
            "--border: #d8e0eb;",
            "--border-strong: #b8c4d4;",
            "--text: #172033;",
            "--muted: #667085;",
            "--accent: #1877f2;",
            "--accent-hover: #166fe5;",
            "--success: #16865f;",
            "--warning: #4f46e5;",
            "--danger: #b83a3a;",
        ):
            assert token in css

        for retired in (
            "#d85c36",
            "#bd4827",
            "rgba(216,92,54,.12)",
            "#a76513",
            "#fff1dc",
            "#edcf9f",
            "#fff8ed",
            "#fff6e9",
            "#714813",
        ):
            assert retired not in css

        assert "background: #242321;" in css
        assert ".nav-item.is-active { background: #3a3733;" in css
        assert ".button-danger" in css
        assert "color: var(--danger);" in css
```

- [x] **Step 2: Chạy test để xác nhận RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_auth_flow.py::test_meta_balanced_theme_css_contract_is_served -q`

Expected: FAIL ở canonical token đầu tiên vì CSS vẫn dùng palette cam/warm cũ.

### Task 2: Triển khai canonical tokens và semantic color mapping

**Files:**
- Modify: `backend/app/static/workspace.css`
- Modify: `backend/app/static/auth.css`
- Modify: `backend/app/static/copilot.css`

**Interfaces:**
- Consumes: test contract từ Task 1.
- Produces: palette canonical được tất cả template đang dùng `workspace.css` kế thừa.

- [x] **Step 1: Đổi root token trong `workspace.css`**

Thay `:root` bằng các token sau, giữ `--surface: #ffffff`:

```css
--background: #f3f6fb;
--surface: #ffffff;
--surface-subtle: #f7f9fc;
--border: #d8e0eb;
--border-strong: #b8c4d4;
--text: #172033;
--muted: #667085;
--accent: #1877f2;
--accent-hover: #166fe5;
--success: #16865f;
--warning: #4f46e5;
--danger: #b83a3a;
```

- [x] **Step 2: Map feedback states trong `workspace.css`**

Dùng các mapping chính xác:

```css
.status.success { background: #ecfdf5; color: var(--success); }
.status.warning { background: #eef2ff; color: var(--warning); }
.status.danger { background: #fff3f3; color: var(--danger); }
.notice { border-color: #bfdbfe; background: #eff6ff; color: #1d4ed8; }
.notice-success { border-color: #a7f3d0; background: #ecfdf5; color: var(--success); }
.session-help, .safety-banner, .approval-warning,
.execution-blockers.execution-warnings {
  border-color: #c7d2fe;
  background: #eef2ff;
  color: #3730a3;
}
```

Giữ `.execution-blockers`, `.password-status-error` và `.button-danger` ở red family. Đổi focus ring thành `rgba(24,119,242,.16)` và các hover/table neutral sang cool blue-gray.

- [x] **Step 3: Cool light surfaces ngoài shared stylesheet**

- `auth.css`: `.auth-page` dùng `var(--background)`; giữ `.auth-brand` dark neutral hiện tại.
- `copilot.css`: thay warm light canvas/surface/text bằng `var(--background)`, `var(--surface-subtle)`, `var(--text)`, `var(--muted)` hoặc blue-gray tương ứng; giữ dark message avatar.
- `fleet.css`: không đổi dark command panel.

- [x] **Step 4: Chạy test GREEN và quét retired colors**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_auth_flow.py::test_meta_balanced_theme_css_contract_is_served tests/test_utf8_ui.py -q`

Expected: PASS.

Run: `rg -n -i '#d85c36|#bd4827|rgba\(216,92,54,.12\)|#a76513|#fff1dc|#edcf9f|#fff8ed|#fff6e9|#714813' backend/app/static -g '*.css'`

Expected: không có kết quả.

### Task 3: Project memory, full verification và local browser smoke

**Files:**
- Modify: `docs/UI_SYSTEM.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-08-03-meta-balanced-theme.md`

**Interfaces:**
- Consumes: theme CSS từ Task 2 và local server `http://127.0.0.1:8010`.
- Produces: canonical UI memory, verification evidence và commit local chưa push/deploy.

- [x] **Step 1: Cập nhật UI system canonical**

Ghi palette blue–indigo–green, semantic mapping và sidebar exception vào `docs/UI_SYSTEM.md`; không duplicate deployment/runtime facts.

- [x] **Step 2: Append changelog sau khi có evidence**

Thêm entry ngày `2026-08-03` với exact test count, compile result, browser smoke pages và trạng thái chưa push/deploy.

- [x] **Step 3: Chạy verification đầy đủ**

Run: `.\.venv\Scripts\python.exe -m pytest`

Expected: toàn bộ test PASS.

Run: `.\.venv\Scripts\python.exe -m compileall -q backend workers`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0.

- [x] **Step 4: Reload và browser smoke local**

Reload Workspace, Campaigns và Hermes Agents trên `http://127.0.0.1:8010`; dùng DOM/computed-style checks và screenshot để xác nhận primary blue, attention indigo, success green, danger red và sidebar `rgb(36, 35, 33)` giữ nguyên.

- [x] **Step 5: Commit local, không push/deploy**

Run:

```powershell
git add -- backend/app/static/workspace.css backend/app/static/auth.css backend/app/static/copilot.css tests/test_auth_flow.py docs/UI_SYSTEM.md docs/CHANGELOG.md docs/superpowers/plans/2026-08-03-meta-balanced-theme.md
git commit -m "Adopt Meta Balanced interface tone"
```

Expected: commit thành công trên `codex/ads-meta-master-branding`; không chạy `git push` hoặc deployment command.
