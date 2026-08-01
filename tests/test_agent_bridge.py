from __future__ import annotations

import httpx
import pytest

from workers.agent.agent_bridge import HermesApiClient, HermesApiError


def test_hermes_api_error_keeps_internal_url_out_of_public_message():
    response = httpx.Response(
        500,
        request=httpx.Request("POST", "http://127.0.0.1:8642/api/sessions/test/chat"),
        text="No LLM provider configured",
    )
    with pytest.raises(HermesApiError) as raised:
        HermesApiClient._ensure_success(response, "chat")

    assert "Hermes Agents" in raised.value.public_message
    assert "127.0.0.1" not in raised.value.public_message
    assert "No LLM provider configured" in raised.value.diagnostic
