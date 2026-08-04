from __future__ import annotations

import json
import sys
from pathlib import Path
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
    {
        "name": "ads_resolve_context",
        "description": (
            "Lấy đúng Facebook profile, worker, ad account và Page/Instagram/Pixel/Form/App đã lưu. "
            "Gọi trước khi lập kế hoạch; noVNC chỉ dùng khi login/2FA/challenge."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "ads_prepare_campaign_work",
        "description": (
            "Nhận kế hoạch đã hiểu từ hội thoại, tự ingest media Telegram/Hermes, tạo action preview "
            "và chờ xác nhận trong chính cuộc trò chuyện. Không cần thao tác form web và chưa publish."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ad_account_id": {"type": "string"},
                "request_text": {"type": "string", "minLength": 1, "maxLength": 12000},
                "title": {"type": "string", "minLength": 1, "maxLength": 240},
                "name": {"type": "string", "minLength": 1, "maxLength": 200},
                "objective": {"type": "string", "minLength": 1, "maxLength": 40},
                "daily_budget_minor": {"type": "integer", "minimum": 1},
                "start_at": {"type": ["string", "null"], "format": "date-time"},
                "end_at": {"type": ["string", "null"], "format": "date-time"},
                "targeting_json": {"type": "object"},
                "creative_json": {"type": "object"},
                "media_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                    "description": "Exact local paths của ảnh/video Hermes đã lưu từ Telegram.",
                },
                "source": {"type": "string", "enum": ["telegram", "hermes", "web", "import"]},
                "source_session_id": {"type": ["string", "null"]},
                "source_message_id": {"type": ["string", "null"]},
            },
            "required": [
                "ad_account_id", "request_text", "title", "name", "objective",
                "daily_budget_minor", "targeting_json", "creative_json"
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_confirm_campaign_work",
        "description": (
            "Sau khi user xác nhận rõ bằng ngôn ngữ tự nhiên, cho worker chạy preflight rồi tự chuyển "
            "sang Campaign → Ad Set → Ad và dừng ở Review. Có thể cancel; không publish."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["execute_draft", "cancel"]},
                "note": {"type": ["string", "null"], "maxLength": 2000},
            },
            "required": ["request_id", "decision"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_get_work_status",
        "description": "Đọc tiến độ, timeline, recovery và artifact của một công việc quảng cáo.",
        "inputSchema": {
            "type": "object",
            "properties": {"request_id": {"type": "string"}},
            "required": ["request_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_list_workflow_learnings",
        "description": "Đọc các phương án recovery đã đề xuất hoặc đã kiểm chứng trên worker này.",
        "inputSchema": {
            "type": "object",
            "properties": {"include_proposed": {"type": "boolean", "default": True}},
            "additionalProperties": False,
        },
    },
    {
        "name": "ads_record_workflow_learning",
        "description": (
            "Ghi một recovery/workflow improvement dưới dạng proposal có cấu trúc. "
            "Không tự sửa source production hoặc tự kích hoạt proposal chưa kiểm chứng."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "learning_key": {"type": "string", "minLength": 1, "maxLength": 160},
                "symptom": {"type": "string", "minLength": 1, "maxLength": 4000},
                "cause": {"type": ["string", "null"], "maxLength": 4000},
                "recovery_plan_json": {"type": "object"},
            },
            "required": ["learning_key", "symptom", "recovery_plan_json"],
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
    if name == "ads_resolve_context":
        return client.call_agent_tool("resource-context")
    if name == "ads_prepare_campaign_work":
        payload = dict(arguments)
        media_paths = list(payload.pop("media_paths", []) or [])
        creative = dict(payload.get("creative_json") or {})
        uploaded: list[dict] = []
        allowed_roots = [
            (client.config.hermes_home or (client.config.data_dir / "hermes")).resolve(),
            (client.config.data_dir / "artifacts").resolve(),
            (client.config.data_dir / "codex" / "uploads").resolve(),
        ]
        for index, raw_path in enumerate(media_paths):
            media_path = Path(str(raw_path)).expanduser().resolve(strict=True)
            if not any(media_path.is_relative_to(root) for root in allowed_roots):
                raise ValueError(f"Media path nằm ngoài vùng Hermes/worker được cấp: {media_path.name}")
            uploaded.append(
                client.upload_agent_media(
                    str(payload["ad_account_id"]),
                    media_path,
                    f"{payload.get('name') or 'Campaign'} — media {index + 1}",
                )
            )
        if uploaded and not creative.get("asset_id"):
            primary = uploaded[0]
            creative["asset_id"] = primary["id"]
            creative["telegram_media_asset_ids"] = [item["id"] for item in uploaded]
        payload["creative_json"] = creative
        payload.setdefault("start_at", None)
        payload.setdefault("end_at", None)
        payload.setdefault("source", "telegram")
        result = client.call_agent_tool("ad-work/prepare", payload)
        result["ingested_media"] = [
            {"id": item["id"], "file_name": item["file_name"], "sha256": item["sha256"]}
            for item in uploaded
        ]
        return result
    if name == "ads_confirm_campaign_work":
        return client.call_agent_tool("ad-work/confirm", arguments)
    if name == "ads_get_work_status":
        return client.call_agent_tool("ad-work/status", {"request_id": arguments["request_id"]})
    if name == "ads_list_workflow_learnings":
        include = "true" if arguments.get("include_proposed", True) else "false"
        return client.call_agent_tool(f"workflow-learnings?include_proposed={include}")
    if name == "ads_record_workflow_learning":
        return client.call_agent_tool("workflow-learnings", arguments)
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
