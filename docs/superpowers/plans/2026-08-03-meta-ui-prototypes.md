# Ads Meta Master UI Prototypes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three standalone, interactive Ads Meta Master UI prototypes that compare the approved visual directions across dashboard, login, and native dialogs.

**Architecture:** A Python standard-library generator owns one semantic prototype document and injects a small variant configuration for palette, elevation, sidebar, metric layout, login identity panel, and dialog treatment. The generator emits three self-contained HTML files and a neutral launcher under `docs/ui-prototypes/`; contract tests verify generated output, UTF-8 copy, variant signatures, interaction hooks, and non-production boundaries.

**Tech Stack:** Python 3.12 standard library, semantic HTML5, inline CSS, native `<dialog>`, vanilla JavaScript, Google Fonts (`Be Vietnam Pro`, `Inter`), Lucide browser CDN, pytest.

## Global Constraints

- Prototype only: do not modify production Jinja templates, API, database, worker, or deployment files.
- Keep the custom Ads Meta Master monogram; do not use official Meta/Facebook logos.
- Preserve semantic colors: success green, attention indigo/amber, danger red `#B83A3A`.
- Every generated document is UTF-8 Vietnamese and includes responsive desktop/tablet/mobile rules.
- Every variant exposes dashboard, login, campaign form dialog, password dialog, and destructive confirmation dialog.
- Preserve the sidebar-left/main-content shell and include breadcrumb, global search, notification bell, Admin menu, filter/sort chips, status pills, and campaign-stage progress.
- Do not add fake charts, decorative sparklines, or a top-navigation replacement.
- No live API calls, credentials, Meta publishing action, or production data.

---

### Task 1: Lock the generated-prototype contract with tests

**Files:**
- Create: `tests/test_ui_prototypes.py`
- Test: `tests/test_ui_prototypes.py`

**Interfaces:**
- Consumes: planned module `scripts.build_meta_ui_prototypes`.
- Produces: contract for `VARIANTS: dict[str, Variant]`, `render_variant(slug: str) -> str`, `render_index() -> str`, and generated output paths.

- [x] **Step 1: Write the failing contract test**

  Add tests that import `VARIANTS`, `OUTPUT_DIR`, `render_variant`, and `render_index`; assert the exact slugs `meta-gradient-vibrant`, `meta-balanced-elevated`, and `meta-dark-sidebar-glass`; verify each render contains UTF-8 metadata, Ads Meta Master copy, all three review screens, all three native dialogs, Lucide initialization, responsive rules, reduced-motion handling, and no mojibake markers.

- [x] **Step 2: Run the focused test and observe RED**

  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ui_prototypes.py -q`

  Expected: collection fails because `scripts.build_meta_ui_prototypes` does not exist.

- [x] **Step 3: Add output-file assertions**

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
- Create: `docs/ui-prototypes/index.html` (generated)
- Create: `docs/ui-prototypes/meta-gradient-vibrant.html` (generated)
- Create: `docs/ui-prototypes/meta-balanced-elevated.html` (generated)
- Create: `docs/ui-prototypes/meta-dark-sidebar-glass.html` (generated)
- Test: `tests/test_ui_prototypes.py`

**Interfaces:**
- Produces: frozen `Variant` dataclass, `VARIANTS`, `render_variant(slug)`, `render_index()`, and `build()`.
- `build()` creates `OUTPUT_DIR`, writes UTF-8 with `newline="\n"`, and emits four deterministic files.

- [x] **Step 1: Define the variant model and exact tokens**

  Implement a frozen dataclass with fields for display name, summary, body/page/sidebar/surface colors, primary/secondary gradient stops, border, text, muted text, shadow levels, radius, and variant CSS additions. Populate all three approved directions without changing semantic danger `#b83a3a` or success `#16865f`.

- [x] **Step 2: Implement one semantic dashboard document**

  Build a shared document containing the custom monogram, real navigation labels, section headers, breadcrumb, global search, notification bell, Admin menu, guardrail banner, four operational metrics, filter/sort chips, ad-account/campaign tables, campaign-stage progress, resource empty state, evaluation switcher, and static sample data. Use semantic table markup and literal Vietnamese status text.

- [x] **Step 3: Implement login and dialog states**

  Add the split login surface, campaign draft dialog, password dialog, destructive confirmation dialog, notification popover, and Admin popover. Add `data-action` hooks, native `showModal()/close()`, state switching, `Escape` support, and visible success feedback that never transmits form values.

- [x] **Step 4: Implement responsive and reduced-motion CSS**

  Add desktop, `max-width: 1120px`, and `max-width: 720px` layouts. Collapse sidebar labels at tablet width, replace the sidebar with compact mobile navigation below 720px, make tables horizontally scrollable, and disable nonessential transitions under `prefers-reduced-motion: reduce`.

- [x] **Step 5: Implement the neutral comparison launcher**

  Render a simple launcher with one short explanation and three direction links. Avoid introducing a fourth visual direction; use neutral white/slate styling and show the exact distinguishing traits of each option.

- [x] **Step 6: Build and run focused tests to reach GREEN**

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
- Consumes: generated files under `docs/ui-prototypes/`.
- Produces: review URLs, screenshots, verification evidence, and a concise memory entry; no production integration decision.

- [x] **Step 1: Run full automated verification**

  Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  .\.venv\Scripts\python.exe -m compileall -q backend workers scripts
  git diff --check
  ```

  Expected: all tests pass, compile exits `0`, and diff check has no output.

- [x] **Step 2: Serve the launcher locally**

  Run a local static server rooted at `docs/ui-prototypes/` on an available loopback port and keep the launcher open for the user. Do not stop or replace the existing app preview on port `8010`.

- [x] **Step 3: Browser-smoke all directions**

  For each direction, inspect dashboard, login, campaign dialog, password dialog, and destructive dialog. Verify at desktop `1440×900`, tablet `1024×768`, and mobile `390×844`; collect screenshots and confirm no browser console errors.

- [x] **Step 4: Record prototype-only status**

  Append a concise changelog entry containing exact test count, local review URL, files produced, and explicit `not pushed/deployed`. Add a UI-system note that these are candidate directions awaiting user selection and are not canonical production styling.

- [x] **Step 5: Mark the plan complete and commit**

  Check completed steps in this plan, stage only prototype/test/UI-memory files, and commit with message:

  ```text
  Build three Ads Meta Master UI prototypes
  ```

  Keep the branch local until the user selects a direction or requests push/deploy.

### Task 4: Refine the selected direction into Meta Light Focus

**Files:**
- Modify: `scripts/build_meta_ui_prototypes.py`
- Modify: `tests/test_ui_prototypes.py`
- Regenerate: `docs/ui-prototypes/*`
- Modify: prototype spec, UI system memory, and changelog

- [x] **Step 1: Lock the selected palette contract with a failing test**

  Require a white sidebar, Meta-blue monogram/action, light canvas, and Direction A login gradient for the legacy Direction C slug. Confirm the test fails against the previous navy/glass implementation.

- [x] **Step 2: Implement and regenerate Meta Light Focus**

  Remove dark/glass/glow styling from Direction C, retain its information layout, and preserve semantic danger/success colors and the stable local URL.

- [x] **Step 3: Verify desktop and mobile in browser**

  Confirm the `248px` white desktop sidebar, blue logo tile, no horizontal overflow, mobile white top bar, scrollable tables, and vivid split login identity panel.

- [x] **Step 4: Run the full suite and commit locally**

  Run the generator, full pytest suite, Python compile, UTF-8/mojibake scan, browser console check, and `git diff --check`; keep the branch unpushed until the user requests integration.

- [x] **Step 5: Expand selected-direction panels to the main-column edges**

  Replace the centered `1420px` content cap with a fluid workspace for Meta Light Focus only. Keep `20px` desktop/tablet gutters and `12px` mobile gutters, then verify at `1920×970` and `390×844` with no horizontal page overflow.

- [x] **Step 6: Simplify navigation, account controls, and dialog chrome**

  Remove the persistent dashboard safety banner, campaign-dialog safety banner, and search shortcut badge; move the Admin popover to a viewport-pinned sidebar footer; change the selected Direction C nav item to a solid filled state with white text; remove decorative top accent lines from every dialog while retaining semantic danger red. Verify the collapsed-sidebar popover stays inside a `1047×910` viewport.

- [x] **Step 7: Restore scannable color and information hierarchy**

  Separate the Meta-blue logo/CTA from an indigo selected navigation state; darken inactive sidebar and dense-data text; strengthen surface borders; give KPI values and markers semantic blue/indigo/amber/green roles; add one matching accent per Ad accounts, Campaign drafts, and Meta resources panel. Verify computed section colors, contrast, and horizontal overflow in browser.
