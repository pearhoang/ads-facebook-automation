from __future__ import annotations

from pathlib import Path


UI_FILES = (
    Path("backend/app/templates/campaigns.html"),
    Path("backend/app/static/campaigns.js"),
    Path("backend/app/static/workspace.css"),
    Path("backend/app/templates/reports.html"),
    Path("backend/app/static/reports.js"),
    Path("backend/app/static/reports.css"),
    Path("backend/app/templates/ai_copilot.html"),
    Path("backend/app/static/ai_copilot.js"),
    Path("backend/app/static/copilot.css"),
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
