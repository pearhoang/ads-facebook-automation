from __future__ import annotations

import json
import sys
from typing import Any

import httpx

from .config import WorkerConfig
from .control_plane import ControlPlaneClient


TOOLS: list[dict[str, Any]] = [
    {
        "name": "ads_workspace_context",
        "description": "Liệt kê workspace và ad account thuộc Bot VPS hiện tại cùng ranh giới an toàn.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "ads_latest_kpi",
        "description": "Đọc KPI snapshot mới nhất. Không mở browser và không thay đổi quảng cáo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad_account_id": {
                    "type": "string",
                    "description": "ID nội bộ của ad account; bỏ trống để lấy mọi account thuộc worker.",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_list_campaign_drafts",
        "description": "Liệt kê campaign draft trong control-plane; không đọc campaign live ngoài Meta.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad_account_id": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_request_kpi_collection",
        "description": "Tạo report job read-only để worker thu thập KPI mới; không cho phép mutation hoặc publish.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad_account_id": {"type": "string"},
                "lookback_days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 7},
            },
            "required": ["ad_account_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_create_campaign_draft",
        "description": (
            "Tạo DRAFT trong control-plane sau khi người dùng yêu cầu rõ ràng. "
            "Tool không gửi duyệt, không chạy browser và không publish."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad_account_id": {"type": "string"},
                "name": {"type": "string", "minLength": 1, "maxLength": 200},
                "objective": {"type": "string", "minLength": 1, "maxLength": 40},
                "daily_budget_minor": {"type": "integer", "minimum": 1},
                "start_at": {"type": ["string", "null"], "format": "date-time"},
                "end_at": {"type": ["string", "null"], "format": "date-time"},
                "targeting_json": {"type": "object"},
                "creative_json": {"type": "object"},
            },
            "required": [
                "ad_account_id",
                "name",
                "objective",
                "daily_budget_minor",
                "targeting_json",
                "creative_json",
            ],
            "additionalProperties": False,
        },
    },
]


def _result(payload: dict) -> dict:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        ],
        "isError": False,
    }


def _error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _call(client: ControlPlaneClient, name: str, arguments: dict) -> dict:
    if name == "ads_workspace_context":
        return client.call_agent_tool("context")
    if name == "ads_latest_kpi":
        return client.call_agent_tool("latest-kpi", {"ad_account_id": arguments.get("ad_account_id")})
    if name == "ads_list_campaign_drafts":
        return client.call_agent_tool(
            "campaign-drafts/query",
            {
                "ad_account_id": arguments.get("ad_account_id"),
                "status": arguments.get("status"),
                "limit": arguments.get("limit", 20),
            },
        )
    if name == "ads_request_kpi_collection":
        return client.call_agent_tool(
            "report-jobs",
            {
                "ad_account_id": arguments["ad_account_id"],
                "lookback_days": arguments.get("lookback_days", 7),
            },
        )
    if name == "ads_create_campaign_draft":
        payload = dict(arguments)
        payload.setdefault("start_at", None)
        payload.setdefault("end_at", None)
        return client.call_agent_tool("campaign-drafts", payload)
    raise ValueError(f"Unknown tool: {name}")


def _handle(client: ControlPlaneClient, message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ads-lush-control-plane", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            payload = _call(client, str(params.get("name") or ""), dict(params.get("arguments") or {}))
            result = _result(payload)
        except (KeyError, ValueError, httpx.HTTPError) as exc:
            detail = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                try:
                    detail = str(exc.response.json().get("detail") or detail)
                except (ValueError, AttributeError):
                    pass
            result = _error(detail[:2000])
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    client = ControlPlaneClient(WorkerConfig.from_env())
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                response = _handle(client, message)
            except Exception as exc:  # MCP boundary: never write diagnostics to stdout.
                request_id = message.get("id") if isinstance(locals().get("message"), dict) else None
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": str(exc)[:2000]},
                }
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
    finally:
        client.close()


if __name__ == "__main__":
    main()
