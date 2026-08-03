# Ads Meta Master — Three UI Prototype Directions

## Status

- Approved by the user on 2026-08-03 through the supplied `implementation_plan.md`.
- This phase produces comparison prototypes only; it does not modify production templates, APIs, worker contracts, database state, or deployment configuration.

## Goal

Create three standalone HTML prototypes for the Ads Meta Master control plane so the user can compare visual directions before selecting one for integration. Every prototype must include the dashboard shell, redesigned native dialogs, and a redesigned login page.

## Reference Hierarchy

1. Product truth and safety copy come from the current Ads Meta Master templates and `docs/UI_SYSTEM.md`.
2. Layout density, table treatment, typography rhythm, and shallow elevation are informed by `D:/vps mới/Youtube_Upload_Lush/final_user_ui.html`.
3. The three visual directions, palettes, and sidebar treatments come from the supplied `implementation_plan.md`.
4. The screenshots are visual references only; the prototype must not imitate Meta Ads Manager so closely that it appears to be an official Meta surface.

## Shared Prototype Contract

- Each direction is a standalone UTF-8 HTML file with inline CSS and JavaScript.
- Each file uses `lang="vi"`, `<meta charset="UTF-8">`, `Be Vietnam Pro` for display text, `Inter` for dense controls/data, and Lucide icons through the pinned CDN URL.
- A compact prototype switcher exposes three review states without page reload: `Dashboard`, `Đăng nhập`, and `Dialogs`.
- Dashboard content uses the real Ads Meta Master information architecture: Facebook accounts, Ad accounts, Campaigns, Báo cáo, Bot VPS, Hermes Agents, and Hermes Dashboard.
- Dashboard sample content is static and explicitly non-production. It shows four operational metrics, campaign/ad-account tables, status badges, an empty resource state, and clear row actions without repeated safety banners.
- The existing left-sidebar plus main-content architecture is preserved. The sidebar becomes denser and more explicit through Lucide icons and the section labels `Điều hướng` and `Quản trị`; no top-navigation redesign is introduced.
- The topbar adds a compact breadcrumb, global search field without a decorative shortcut badge, and notification bell. The concise Admin menu lives at the bottom of the sidebar so account controls have one stable home.
- Campaign tables add useful filter/sort chips, literal status pills, and one compact `Campaign → Ad Set → Ad → Review` progress treatment. No fake chart or decorative sparkline is added.
- Dialog coverage includes:
  - a structured `Tạo campaign draft` form dialog;
  - the shared `Đổi mật khẩu` dialog;
  - a destructive confirmation dialog where danger remains red.
- Dialog headers use a simple bottom divider and no decorative top accent line; campaign forms do not add an extra safety-banner block.
- Login coverage includes username/password, explicit sign-in action, a restrained product value panel, and no public-signup affordance.
- The custom Ads Meta Master monogram is used instead of an official Meta or Facebook logo.
- Responsive behavior is evaluated at desktop `1440×900`, tablet `1024×768`, and mobile `390×844`.
- Animation is limited to 120–200 ms state feedback; `prefers-reduced-motion` disables nonessential transitions.

## Direction A — Meta Gradient Vibrant

- Sidebar uses a vertical `#0668E1 → #8B5CF6 → #EC4899` gradient with white navigation.
- Primary actions use a restrained blue-to-violet gradient; semantic success/warning/danger colors remain separate.
- Metrics use four separate raised tiles with narrow color accents and small Lucide icons.
- Header uses a light translucent surface; cards use shallow shadows and one controlled hover lift.
- Login uses a vivid brand panel beside a high-contrast white form.
- Dialogs keep a solid readable body and a plain header without an ornamental accent line.

## Direction B — Meta Balanced Elevated

- Sidebar uses `#1E293B → #334155` with a thin brand accent line and functional section labels.
- Primary actions use solid `#0668E1`; gradient appears only in selected navigation.
- Metrics remain one elevated four-column strip, matching the strongest pattern from the YouTube reference.
- Tables and forms rely mainly on borders, spacing, and type hierarchy; shadows stay shallow.
- Login is a restrained split layout with a slate brand panel and blue action emphasis.
- Dialogs use a normal centered overlay, clear section grouping, and minimal effects.

## Direction C — Meta Light Focus (user-selected refinement)

- The user selected Direction C on 2026-08-03, then requested a calmer Meta-style light shell while preserving its uncluttered structure.
- Sidebar uses solid white with a soft gray-blue border and slate `#344054` navigation text. The selected row uses a pale blue–lavender gradient, indigo text/icon, a thin periwinkle border, and a shallow shadow; it reads as selection without competing with solid Meta-blue CTAs. Pink remains reserved for brand/avatar identity.
- The sidebar brand band uses a light blue–violet–pink Meta gradient. The blue monogram keeps a white halo for separation, while the Admin avatar uses the saturated version of the same gradient with white text.
- Main canvas uses `#F1F4F8`, opaque white surfaces, stronger neutral borders, shallow neutral shadows, and solid `#0866FF` primary actions.
- On desktop and tablet, the workspace is fluid rather than centered in a fixed `max-width`: panels use the full main-column width with a `20px` horizontal gutter, matching the denser YouTube control-plane reference. Mobile retains a `12px` gutter.
- The refined KPI treatment removes Direction C's separate tiles and consolidates metrics into one divided strip without glass, glow, or decorative haze. Icons become small inline label marks without background boxes; values carry the hierarchy, and each centered bottom marker retains its semantic color. Mobile presents the same strip as a `2×2` grid.
- Information hierarchy uses a restrained blue–indigo–amber–green system: blue for account/action, indigo for campaign/selection, amber for pending attention, and green for ready/approved/resource. KPI values and short bottom markers carry these roles; panel headers repeat only their relevant section accent.
- Login intentionally borrows Direction A's `#0668E1 → #8B5CF6 → #EC4899` identity panel so authentication does not feel visually empty.
- Dialog bodies remain opaque and stable; headers have no top accent line, destructive actions remain `#B83A3A`, and the backdrop does not use blur.
- The legacy slug `meta-dark-sidebar-glass` is retained so the existing local review URL remains stable during selection.

## Interaction And Accessibility

- All clickable controls have visible hover and `:focus-visible` states.
- Dialogs use native `<dialog>`, close on `Escape`, close from explicit cancel/close controls, and return focus to the trigger where supported.
- Form labels are always visible above fields. Helper text remains concrete and safety-focused.
- Tables retain semantic `<table>`, `<thead>`, `<tbody>`, and scoped column headers.
- Search, notification, and Admin menu interactions are local prototype behavior only; they never call a backend.
- Color is never the only state indicator; status badges include literal text and icons.
- Mobile hides the fixed sidebar and exposes a compact top navigation while preserving the primary task and action.

## Non-Goals

- Do not apply a selected direction to Jinja templates in this phase.
- Do not add runtime dependencies, migrations, API calls, real credentials, or live production data.
- Do not push or deploy prototypes without a separate user request.
- Do not redesign the Hermes native dashboard or Meta Ads Manager itself.

## Acceptance Criteria

- Exactly three standalone direction files plus one neutral comparison launcher exist under `docs/ui-prototypes/`.
- Dashboard, login, campaign dialog, password dialog, and destructive dialog can be exercised in every direction.
- Variant palette signatures are distinct and automated tests reject missing screens, missing UTF-8 declarations, broken Vietnamese text, or absent danger styling.
- Browser smoke captures each direction at desktop and at least the login/dialog state, with no console errors.
