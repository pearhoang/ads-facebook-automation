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

    assert "--page: #f5f7fa" in html
    assert "--surface: #ffffff" in html
    assert "--sidebar-text: #1c1e21" in html
    assert "--sidebar-muted: #65676b" in html
    assert ".brand > .brand-mark" in html
    assert "background: #0866ff" in html
    assert "color: #fff" in html
    assert "linear-gradient(135deg, #0668e1, #8b5cf6 58%, #ec4899)" in html
    assert 'body[data-variant="meta-dark-sidebar-glass"] .content {' in html
    assert "width: 100%" in html
    assert "max-width: none" in html
    assert "padding-inline: 20px" in html
