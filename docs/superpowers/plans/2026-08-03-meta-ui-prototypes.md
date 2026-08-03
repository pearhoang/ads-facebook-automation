# Ads Meta Master UI Prototypes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three standalone, interactive Ads Meta Master UI prototypes that compare the approved visual directions across dashboard, login, and native dialogs.

**Architecture:** A Python standard-library generator owns one semantic prototype document and injects a small variant configuration for palette, elevation, sidebar, metric layout, login identity panel, and dialog treatment. The generator emits three self-contained HTML files and a neutral launcher under `output/ui-prototypes/`; contract tests verify generated output, UTF-8 copy, variant signatures, interaction hooks, and non-production boundaries.

**Tech Stack:** Python 3.12 standard library, semantic HTML5, inline CSS, native `<dialog>`, vanilla JavaScript, Google Fonts (`Be Vietnam Pro`, `Inter`), Lucide browser CDN, pytest.

## Global Constraints

- Prototype only: do not modify production Jinja templates, API, database, worker, or deployment files.
- Keep the custom Ads Meta Master monogram; do not use official Meta/Facebook logos.
- Preserve semantic colors: success green, attention indigo/amber, danger red `#B83A3A`.
- Every generated document is UTF-8 Vietnamese and includes responsive desktop/tablet/mobile rules.
- Every variant exposes dashboard, login, campaign form dialog, password dialog, and destructive confirmation dialog.
- No live API calls, credentials, Meta publishing action, or production data.

---

### Task 1: Lock the generated-prototype contract with tests

**Files:**
- Create: `tests/test_ui_prototypes.py`
- Test: `tests/test_ui_prototypes.py`

**Interfaces:**
- Consumes: planned module `scripts.build_meta_ui_prototypes`.
- Produces: contract for `VARIANTS: dict[str, Variant]`, `render_variant(slug: str) -> str`, `render_index() -> str`, and generated output paths.

- [ ] **Step 1: Write the failing contract test**

  Add tests that import `VARIANTS`, `OUTPUT_DIR`, `render_variant`, and `render_index`; assert the exact slugs `meta-gradient-vibrant`, `meta-balanced-elevated`, and `meta-dark-sidebar-glass`; verify each render contains UTF-8 metadata, Ads Meta Master copy, all three review screens, all three native dialogs, Lucide initialization, responsive rules, reduced-motion handling, and no mojibake markers.

- [ ] **Step 2: Run the focused test and observe RED**

  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ui_prototypes.py -q`

  Expected: collection fails because `scripts.build_meta_ui_prototypes` does not exist.

- [ ] **Step 3: Add output-file assertions**

  Assert that every generated file equals `render_variant(slug)`, the launcher equals `render_index()`, and each direction contains its exact palette signature:

  ```python
  expected_tokens = {
      "meta-gradient-vibrant": ("#0668e1", "#ec4899"),
      "meta-balanced-elevated": ("#1e293b", "#0668e1"),
      "meta-dark-sidebar-glass": ("#0f172a", "#6366f1"),
  }
  ```

### Task 2: Implement the prototype generator and launcher

**Files:**
- Create: `scripts/build_meta_ui_prototypes.py`
- Create: `output/ui-prototypes/index.html` (generated)
- Create: `output/ui-prototypes/meta-gradient-vibrant.html` (generated)
- Create: `output/ui-prototypes/meta-balanced-elevated.html` (generated)
- Create: `output/ui-prototypes/meta-dark-sidebar-glass.html` (generated)
- Test: `tests/test_ui_prototypes.py`

**Interfaces:**
- Produces: frozen `Variant` dataclass, `VARIANTS`, `render_variant(slug)`, `render_index()`, and `build()`.
- `build()` creates `OUTPUT_DIR`, writes UTF-8 with `newline="\n"`, and emits four deterministic files.

- [ ] **Step 1: Define the variant model and exact tokens**

  Implement a frozen dataclass with fields for display name, summary, body/page/sidebar/surface colors, primary/secondary gradient stops, border, text, muted text, shadow levels, radius, and variant CSS additions. Populate all three approved directions without changing semantic danger `#b83a3a` or success `#16865f`.

- [ ] **Step 2: Implement one semantic dashboard document**

  Build a shared document containing the custom monogram, real navigation labels, guardrail banner, four operational metrics, ad-account/campaign tables, resource empty state, evaluation switcher, and static sample data. Use semantic table markup and literal Vietnamese status text.

- [ ] **Step 3: Implement login and dialog states**

  Add the split login surface, campaign draft dialog, password dialog, and destructive confirmation dialog. Add `data-action` hooks, native `showModal()/close()`, state switching, `Escape` support, and visible success feedback that never transmits form values.

- [ ] **Step 4: Implement responsive and reduced-motion CSS**

  Add desktop, `max-width: 1120px`, and `max-width: 720px` layouts. Collapse sidebar labels at tablet width, replace the sidebar with compact mobile navigation below 720px, make tables horizontally scrollable, and disable nonessential transitions under `prefers-reduced-motion: reduce`.

- [ ] **Step 5: Implement the neutral comparison launcher**

  Render a simple launcher with one short explanation and three direction links. Avoid introducing a fourth visual direction; use neutral white/slate styling and show the exact distinguishing traits of each option.

- [ ] **Step 6: Build and run focused tests to reach GREEN**

  Run:

  ```powershell
  .\.venv\Scripts\python.exe scripts\build_meta_ui_prototypes.py
  .\.venv\Scripts\python.exe -m pytest tests\test_ui_prototypes.py -q
  ```

  Expected: generator writes four files and all prototype contract tests pass.

### Task 3: Visual verification and project memory

**Files:**
- Modify: `docs/UI_SYSTEM.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/plans/2026-08-03-meta-ui-prototypes.md`

**Interfaces:**
- Consumes: generated files under `output/ui-prototypes/`.
- Produces: review URLs, screenshots, verification evidence, and a concise memory entry; no production integration decision.

- [ ] **Step 1: Run full automated verification**

  Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\python.exe -m compileall -q backend workers scripts
  git diff --check
  ```

  Expected: all tests pass, compile exits `0`, and diff check has no output.

- [ ] **Step 2: Serve the launcher locally**

  Run a local static server rooted at `output/ui-prototypes/` on an available loopback port and keep the launcher open for the user. Do not stop or replace the existing app preview on port `8010`.

- [ ] **Step 3: Browser-smoke all directions**

  For each direction, inspect dashboard, login, campaign dialog, password dialog, and destructive dialog. Verify at desktop `1440×900`, tablet `1024×768`, and mobile `390×844`; collect screenshots and confirm no browser console errors.

- [ ] **Step 4: Record prototype-only status**

  Append a concise changelog entry containing exact test count, local review URL, files produced, and explicit `not pushed/deployed`. Add a UI-system note that these are candidate directions awaiting user selection and are not canonical production styling.

- [ ] **Step 5: Mark the plan complete and commit**

  Check completed steps in this plan, stage only prototype/test/UI-memory files, and commit with message:

  ```text
  Build three Ads Meta Master UI prototypes
  ```

  Keep the branch local until the user selects a direction or requests push/deploy.

