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
