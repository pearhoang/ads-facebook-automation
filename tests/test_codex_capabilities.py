from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from workers.agent import codex_capabilities, codex_capabilities_mcp


def _jwt(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_codex_status_reads_local_oauth_without_exposing_tokens(tmp_path: Path):
    auth_path = tmp_path / "codex" / "auth.json"
    auth_path.parent.mkdir()
    claim = {
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct_test",
            "chatgpt_plan_type": "plus",
        },
        "email": "owner@example.test",
        "exp": 4_102_444_800,
    }
    auth_path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": _jwt(claim),
                    "refresh_token": "refresh-secret",
                    "id_token": _jwt(claim),
                }
            }
        ),
        encoding="utf-8",
    )

    status = codex_capabilities.capability_status(auth_path)

    assert status == {
        "configured": True,
        "credential_present": True,
        "disconnected": False,
        "account_id": "acct_test",
        "email": "owner@example.test",
        "plan_type": "plus",
        "refreshable": True,
    }
    assert "refresh-secret" not in json.dumps(status)


def test_disconnect_marker_blocks_existing_credential(tmp_path: Path):
    auth_path = tmp_path / "codex" / "auth.json"
    auth_path.parent.mkdir()
    auth_path.write_text('{"tokens": {"access_token": "ignored"}}', encoding="utf-8")
    codex_capabilities.disconnect_marker_path(auth_path).write_text("", encoding="utf-8")

    assert codex_capabilities.capability_status(auth_path) == {
        "configured": False,
        "credential_present": True,
        "disconnected": True,
    }
    with pytest.raises(RuntimeError, match="đã ngắt kết nối"):
        codex_capabilities.load_credential(auth_path)


def test_search_request_matches_pi_extension_contract():
    payload = codex_capabilities.build_search_request(
        query="Meta Ads updates",
        recency_days=7,
        allowed_domains=["https://facebook.com/docs"],
        context_size="high",
        response_length="short",
    )
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["commands"] == {
        "search_query": [{"q": "Meta Ads updates", "recency": 7, "domains": ["facebook.com"]}],
        "response_length": "short",
    }
    assert payload["settings"]["search_context_size"] == "high"
    assert payload["settings"]["external_web_access"] == "live"


def test_codex_mcp_exposes_only_search_and_vision(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    listed = codex_capabilities_mcp._handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    assert {item["name"] for item in listed["result"]["tools"]} == {
        "codex_search",
        "codex_vision",
    }

    called = codex_capabilities_mcp._handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "codex_search", "arguments": {"query": "latest Meta Ads"}},
        }
    )
    assert called["result"]["isError"] is True
    assert "Kết nối Codex" in called["result"]["content"][0]["text"]


def test_vision_rejects_paths_outside_worker_roots(tmp_path: Path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"not-an-image")
    with pytest.raises(ValueError, match="ngoài vùng dữ liệu"):
        codex_capabilities.validate_image_paths(
            [str(outside)],
            allowed_roots=[tmp_path / "worker-data"],
        )
