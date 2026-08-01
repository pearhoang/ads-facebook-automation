from __future__ import annotations

from pathlib import Path

from workers.agent import browser_runtime


def test_snap_launcher_is_unwrapped_to_isolated_binary(
    monkeypatch,
    tmp_path: Path,
):
    direct = tmp_path / "chrome"
    direct.write_text("#!/bin/sh\n", encoding="utf-8")
    direct.chmod(0o755)
    monkeypatch.setenv("BROWSER_SESSION_SNAP_DIRECT_BIN", str(direct))
    monkeypatch.setattr(browser_runtime, "_is_snap_chromium", lambda _value: True)

    assert browser_runtime._prefer_direct_snap_chromium("/snap/bin/chromium") == str(direct)


def test_snap_bin_path_is_detected_before_symlink_resolution():
    assert browser_runtime._is_snap_chromium("/snap/bin/chromium") is True


def test_native_chromium_path_is_not_rewritten(monkeypatch):
    monkeypatch.setattr(browser_runtime, "_is_snap_chromium", lambda _value: False)

    assert browser_runtime._prefer_direct_snap_chromium("/usr/bin/google-chrome") == (
        "/usr/bin/google-chrome"
    )
