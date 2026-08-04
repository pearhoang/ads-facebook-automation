from pathlib import Path

from scripts.build_meta_ui_prototypes import (
    OUTPUT_DIR,
    VARIANTS,
    build,
    render_index,
    render_variant,
)


EXPECTED_VARIANTS = {
    "meta-gradient-vibrant": (
        "--sidebar-start: #0668e1",
        "--sidebar-end: #ec4899",
    ),
    "meta-balanced-elevated": (
        "--sidebar-start: #1e293b",
        "--primary: #0668e1",
    ),
    "meta-dark-sidebar-glass": (
        "--sidebar-start: #ffffff",
        "--primary: #0866ff",
    ),
}

MOJIBAKE_MARKERS = ("Ã", "Â", "Æ", "áº", "á»", "�")


def test_rendered_variants_expose_every_review_state_and_dialog() -> None:
    """Removing a review screen or native dialog must break the prototype contract."""

    assert set(VARIANTS) == set(EXPECTED_VARIANTS)

    for slug in EXPECTED_VARIANTS:
        html = render_variant(slug)

        assert '<html lang="vi"' in html
        assert '<meta charset="UTF-8">' in html
        assert f'data-variant="{slug}"' in html
        assert "Ads Meta Master" in html
        assert "Meta Ads Automation" in html
        assert 'data-screen="dashboard"' in html
        assert 'data-screen="login"' in html
        assert 'id="campaign-dialog"' in html
        assert 'id="password-dialog"' in html
        assert 'id="danger-dialog"' in html
        assert "lucide.createIcons()" in html
        assert "@media (max-width: 1120px)" in html
        assert "@media (max-width: 720px)" in html
        assert "prefers-reduced-motion: reduce" in html
        assert not any(marker in html for marker in MOJIBAKE_MARKERS)


def test_variants_have_distinct_brand_signatures_and_shared_safety_colors() -> None:
    """Collapsing the three directions or recoloring danger as brand is a regression."""

    rendered = {slug: render_variant(slug).lower() for slug in EXPECTED_VARIANTS}

    for slug, signatures in EXPECTED_VARIANTS.items():
        for signature in signatures:
            assert signature in rendered[slug]
        assert "--danger: #b83a3a" in rendered[slug]
        assert "--success: #16865f" in rendered[slug]
        assert "xóa bản nháp" in rendered[slug]

    assert len(set(rendered.values())) == 3


def test_build_writes_deterministic_standalone_files(tmp_path: Path) -> None:
    """A build must emit portable UTF-8 files matching the renderer exactly."""

    written = build(tmp_path)

    assert {path.name for path in written} == {
        "index.html",
        "meta-gradient-vibrant.html",
        "meta-balanced-elevated.html",
        "meta-dark-sidebar-glass.html",
    }
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == render_index()
    for slug in EXPECTED_VARIANTS:
        assert (tmp_path / f"{slug}.html").read_text(
            encoding="utf-8"
        ) == render_variant(slug)


def test_committed_prototypes_match_the_generator() -> None:
    """Review files must never drift from their committed generator source."""

    assert (OUTPUT_DIR / "index.html").read_text(encoding="utf-8") == render_index()
    for slug in EXPECTED_VARIANTS:
        assert (OUTPUT_DIR / f"{slug}.html").read_text(
            encoding="utf-8"
        ) == render_variant(slug)


def test_launcher_links_all_directions_without_becoming_a_fourth_theme() -> None:
    """The launcher must expose exactly the three approved options."""

    html = render_index()

    assert html.count('class="direction-link"') == 3
    for slug in EXPECTED_VARIANTS:
        assert f'href="{slug}.html"' in html
    assert "Chọn hướng giao diện để xem" in html
    assert "data-variant=" not in html


def test_lucide_replacement_selectors_target_rendered_svg_elements() -> None:
    """Sizing icons through removed <i> nodes would break their mobile layout."""

    html = render_variant("meta-balanced-elevated")

    assert ".global-search > svg {" in html
    assert ".button svg {" in html
    assert ".dialog-close svg {" in html
    assert ".global-search i {" not in html


def test_login_prototype_never_embeds_a_plaintext_password() -> None:
    """Embedding a sample password would violate the product's secret boundary."""

    for slug in EXPECTED_VARIANTS:
        html = render_variant(slug)

        assert 'id="login-password"' in html
        assert 'autocomplete="current-password"' in html
        assert 'value="1234"' not in html


def test_selected_direction_uses_meta_light_shell_and_vibrant_login() -> None:
    """Dark sidebar or a muted monogram must not return after direction C is selected."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert "--page: #f1f4f8" in html
    assert "--surface: #ffffff" in html
    assert "--sidebar-text: #172033" in html
    assert "--sidebar-muted: #344054" in html
    assert ".brand > .brand-mark" in html
    assert "radial-gradient(ellipse 820px 390px at 0 0" in html
    assert "radial-gradient(ellipse 820px 390px at -248px 0" in html
    assert "radial-gradient(ellipse 820px 390px at -82px 0" in html
    assert "rgba(255,218,202,.60)" in html
    assert "rgba(255,238,231,.28)" in html
    assert "radial-gradient(ellipse 720px 330px at 0 0" in html
    assert "rgba(169,244,220,.46)" in html
    assert "rgba(219,232,255,.17)" in html
    assert "linear-gradient(145deg, #fbfcfe 0%, #f7f8fb 54%, #f8f7fb 100%)" in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .brand {' in html
    assert "background: transparent" in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .topbar {' in html
    assert 'rel="icon" type="image/svg+xml" sizes="any"' in html
    assert "stroke='%230866ff'" in html
    assert "color: #fff" in html
    assert "linear-gradient(135deg, #0668e1, #8b5cf6 58%, #ec4899)" in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .content {' in html
    assert "width: 100%" in html
    assert "max-width: none" in html
    assert "padding-inline: 20px" in html


def test_selected_workspace_removes_decorative_chrome_and_uses_sidebar_account() -> None:
    """The selected shell must stay product-like without banner or topbar account clutter."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert '<div class="notice">' not in html
    assert 'class="search-key"' not in html
    assert '<button class="avatar-button"' not in html
    assert 'class="sidebar-account-button"' in html
    assert 'class="popover sidebar-account-popover hidden"' in html
    assert 'data-popover-toggle="admin"' in html
    assert 'class="dialog-notice"' not in html
    assert "background: #4f46e5" in html
    assert "box-shadow: inset 3px 0 0 #0866ff" not in html
    assert "dialog-head::before" not in html


def test_sidebar_account_stays_inside_the_viewport_shell() -> None:
    """Letting the desktop shell grow with content would push the account footer off-screen."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert "height: 100vh" in html
    assert ".shell { height: auto; min-height: 100dvh; }" in html
    assert ".sidebar-account-popover { top: auto" in html


def test_selected_workspace_has_scannable_color_hierarchy() -> None:
    """Direction C needs distinct brand, navigation, section, and semantic color roles."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert "--page: #f1f4f8" in html
    assert "--muted: #475467" in html
    assert "--sidebar-muted: #344054" in html
    assert "border: 1px solid #4f46e5" in html
    assert "background: #4f46e5" in html
    assert "background: #4338ca" in html
    assert "box-shadow: 0 4px 10px rgba(79,70,229,.22)" in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .primary-button {' in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .primary-button:hover {' in html
    assert "linear-gradient(115deg" not in html
    assert ".metric::after" in html
    assert ".metric-value" in html and "color: var(--metric-accent)" in html
    assert ".card-accounts { --section-accent: #0866ff; }" in html
    assert ".card-campaigns { --section-accent: #4f46e5; }" in html
    assert ".card-resources { --section-accent: #0f8f6f; }" in html
    assert 'class="card card-accounts"' in html
    assert 'class="card card-campaigns"' in html
    assert 'class="card card-resources"' in html


def test_selected_workspace_uses_quiet_sidebar_and_data_first_kpi_strip() -> None:
    """Brand and account chrome must stay quiet so selected navigation and data lead."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert "linear-gradient(110deg, #e6f0ff 0%, #f0ebff 54%, #ffe9f3 100%)" not in html
    assert 'viewbox="0 0 42 28"' in html
    assert 'd="m3 14c7 4 13 4 21 14c29 24 35 24 39 14c35 4 29 4 21 14c13 24 7 24 3 14z"' in html
    assert 'class="avatar account-brand-mark"' in html
    assert '<span class="avatar">a</span>' not in html
    assert ".sidebar-footer .account-brand-mark" in html
    assert "background: transparent" in html
    assert "color: #6674d9" in html
    assert "linear-gradient(135deg, #0866ff 0%, #7c3aed 56%, #ec4899 100%)" not in html
    assert ".metrics {" in html
    assert "gap: 0" in html
    assert ".metric-icon" in html
    assert "width: 15px" in html
    assert "background: transparent" in html
    assert "left: 50%" in html
    assert "transform: translatex(-50%)" in html


def test_selected_workspace_reduces_panel_chrome_and_increases_readability() -> None:
    """Dense workspace content needs stronger type and fewer decorative header layers."""

    html = render_variant("meta-dark-sidebar-glass").lower()

    assert ".card-head::before" in html and "content: none" in html
    assert ".section-copy p" in html and "display: none" in html
    assert "table {\n  font-size: 12.5px" in html
    assert ".item-meta" in html and "font-size: 10.5px" in html
    assert ".section-icon" in html and "background: transparent" in html
