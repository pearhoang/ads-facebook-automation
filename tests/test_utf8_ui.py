from __future__ import annotations

from pathlib import Path


UI_FILES = (
    Path("backend/app/templates/_sidebar.html"),
    Path("backend/app/templates/_topbar_tools.html"),
    Path("backend/app/templates/login.html"),
    Path("backend/app/templates/campaigns.html"),
    Path("backend/app/static/campaigns.js"),
    Path("backend/app/templates/ad_accounts.html"),
    Path("backend/app/static/ad_accounts.js"),
    Path("backend/app/static/ui.js"),
    Path("backend/app/static/workspace.css"),
    Path("backend/app/static/ui-icons.svg"),
    Path("backend/app/static/auth.css"),
    Path("backend/app/templates/reports.html"),
    Path("backend/app/static/reports.js"),
    Path("backend/app/static/reports.css"),
    Path("backend/app/templates/ai_copilot.html"),
    Path("backend/app/static/ai_copilot.js"),
    Path("backend/app/static/copilot.css"),
    Path("backend/app/templates/hermes_agents.html"),
    Path("backend/app/static/hermes_agents.js"),
)


def test_campaign_ui_files_are_utf8_without_mojibake_markers():
    combined = ""
    for path in UI_FILES:
        text = path.read_bytes().decode("utf-8")
        combined += text
        assert "\ufffd" not in text
        assert not any(
            marker in text
            for marker in ("Ä‘", "Ä", "Æ°", "á»‹", "áº¡", "Â·", "â€”", "â†’")
        )

    assert '<meta charset="UTF-8">' in combined
    assert "Đã cập nhật ad account" in combined
    assert "Múi giờ" in combined
    assert "Thu thập KPI" in combined
    assert "Chỉ đọc Ads Manager" in combined
    assert "Đính kèm tệp văn bản" in combined
    assert "Gõ / để xem shortcut" in combined
    assert "Experimental Full Access" in combined
    assert "Quyền Agent" in combined


def test_copilot_attachment_trigger_is_compact_and_inside_composer_input():
    template = Path("backend/app/templates/ai_copilot.html").read_text(encoding="utf-8")
    styles = Path("backend/app/static/copilot.css").read_text(encoding="utf-8")

    shell_start = template.index('<div class="composer-input-shell">')
    shell_end = template.index("</div>", shell_start)
    shell = template[shell_start:shell_end]
    assert 'id="attach-file"' in shell
    assert '<span aria-hidden="true">+</span>' in shell
    assert 'id="composer-input"' in shell
    assert ".composer-input-shell { position: relative;" in styles
    assert ".composer .attach-file { position: absolute;" in styles


def test_primary_navigation_uses_native_hermes_dashboard():
    active_templates = (
        Path("backend/app/templates/workspace.html"),
        Path("backend/app/templates/ad_accounts.html"),
        Path("backend/app/templates/campaigns.html"),
        Path("backend/app/templates/reports.html"),
        Path("backend/app/templates/bot_nodes.html"),
        Path("backend/app/templates/hermes_agents.html"),
    )
    for path in active_templates:
        text = path.read_text(encoding="utf-8")
        assert ">AI Copilot<" not in text
        assert '{% include "_sidebar.html" %}' in text

    sidebar = Path("backend/app/templates/_sidebar.html").read_text(encoding="utf-8")
    assert "Hermes Dashboard" in sidebar
    assert 'href="/ai-copilot"' in sidebar
    assert "data-account-menu-toggle" in sidebar
    assert "data-global-logout" in sidebar

    hermes_agents = active_templates[-1].read_text(encoding="utf-8")
    assert "Mở Hermes Dashboard" in hermes_agents


def test_canonical_app_keeps_prototype_topbar_and_kpi_anatomy():
    active_templates = (
        Path("backend/app/templates/workspace.html"),
        Path("backend/app/templates/campaigns.html"),
        Path("backend/app/templates/reports.html"),
        Path("backend/app/templates/bot_nodes.html"),
        Path("backend/app/templates/hermes_agents.html"),
    )
    for path in active_templates:
        text = path.read_text(encoding="utf-8")
        assert 'class="breadcrumb"' in text
        assert '{% include "_topbar_tools.html" %}' in text
        assert 'class="content-pane"' in text

    for path in active_templates[:4]:
        text = path.read_text(encoding="utf-8")
        assert 'class="metric-icon"' in text

    tools = Path("backend/app/templates/_topbar_tools.html").read_text(encoding="utf-8")
    sidebar = Path("backend/app/templates/_sidebar.html").read_text(encoding="utf-8")
    script = Path("backend/app/static/ui.js").read_text(encoding="utf-8")
    styles = Path("backend/app/static/workspace.css").read_text(encoding="utf-8")
    assert "data-global-search" in tools
    assert "data-notification-popover" in tools
    assert "applyGlobalSearch" in script
    assert "renderNotifications" in script
    assert ".global-search" in styles
    assert ".notification-popover" in styles
    assert ".metric-icon svg" in styles
    assert ".content-pane" in styles
    assert "#ad-accounts table" in styles
    assert "min-width: 900px; table-layout: auto" in styles
    assert ".empty-state[hidden] { display: none; }" in styles
    assert ".row-button" in styles
    assert '.breadcrumb svg:nth-of-type(2)' not in styles
    assert 'class="brand-mark" aria-hidden="true"' in sidebar
    assert 'class="avatar account-brand-mark" aria-hidden="true"' in sidebar
    assert "gap: 18px" in styles
    assert ".section-icon svg" in styles


def test_ad_account_setup_is_separate_from_agent_work_monitoring():
    setup_template = Path("backend/app/templates/ad_accounts.html").read_text(encoding="utf-8")
    setup_script = Path("backend/app/static/ad_accounts.js").read_text(encoding="utf-8")
    work_template = Path("backend/app/templates/campaigns.html").read_text(encoding="utf-8")
    work_script = Path("backend/app/static/campaigns.js").read_text(encoding="utf-8")
    icons = Path("backend/app/static/ui-icons.svg").read_text(encoding="utf-8")

    assert 'byId("ad-accounts-empty").hidden = state.adAccounts.length > 0' in setup_script
    assert 'data-edit-ad-account=' in setup_script
    assert 'class="row-button"' in setup_script
    assert 'id="ad-account-dialog"' in setup_template
    assert 'id="resource-dialog"' in setup_template
    assert 'id="work-requests-body"' in work_template
    assert 'api("/api/ad-automation-requests")' in work_script
    assert 'id="campaign-form"' not in work_template
    assert "openCampaignDialog" not in work_script
    assert 'id="pencil"' in icons
    assert 'id="arrow-up-right"' in icons


def test_agent_work_detail_keeps_canonical_dialog_and_timeline_anatomy():
    template = Path("backend/app/templates/campaigns.html").read_text(encoding="utf-8")
    styles = Path("backend/app/static/workspace.css").read_text(encoding="utf-8")

    assert 'id="work-detail-dialog" class="wide-dialog work-detail-dialog"' in template
    assert 'id="work-detail-timeline" class="work-timeline"' in template
    assert 'id="work-handoff-link"' in template
    assert ".work-detail-grid" in styles
    assert ".work-timeline" in styles
    assert ".timeline-marker" in styles


def test_canonical_selects_are_progressively_enhanced_without_changing_form_contracts():
    script = Path("backend/app/static/ui.js").read_text(encoding="utf-8")
    styles = Path("backend/app/static/workspace.css").read_text(encoding="utf-8")

    assert 'document.querySelectorAll("select").forEach(enhanceSelect)' in script
    assert 'menu.setAttribute("popover", "auto")' in script
    assert 'menu.setAttribute("role", "listbox")' in script
    assert "const gap = 4" in script
    assert "select.dispatchEvent(new Event(\"change\"" in script
    assert ".ui-select-menu" in styles
    assert "border-radius: 10px" in styles
    assert "min-height: 31px" in styles
    assert ".ui-select-native" in styles
