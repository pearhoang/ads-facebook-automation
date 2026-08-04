from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

from . import codex_capabilities


TOOLS = [
    {
        "name": "codex_search",
        "description": (
            "Tìm kiếm web hiện tại qua Codex OAuth trên worker. Dùng khi model chính không có "
            "web search hoặc câu hỏi cần dữ liệu mới; tóm tắt và giữ URL nguồn trong câu trả lời."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 4000},
                "recency_days": {"type": "integer", "minimum": 1},
                "allowed_domains": {"type": "array", "items": {"type": "string"}},
                "blocked_domains": {"type": "array", "items": {"type": "string"}},
                "context_size": {"type": "string", "enum": ["low", "medium", "high"]},
                "response_length": {"type": "string", "enum": ["short", "medium", "long"]},
                "include_image_results": {"type": "boolean"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "codex_vision",
        "description": (
            "Phân tích ảnh bằng Codex vision khi model chính chỉ nhận text. Chỉ đọc ảnh trong "
            "Hermes/worker data đã được cấp và không sửa tệp nguồn."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "minLength": 1, "maxLength": 12000},
                "image_paths": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {"type": "string", "minLength": 1},
                },
                "model": {"type": "string", "minLength": 1, "maxLength": 120},
            },
            "required": ["prompt", "image_paths"],
            "additionalProperties": False,
        },
    },
]


def _result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _paths() -> tuple[Path, list[Path]]:
    worker_data = Path(os.getenv("WORKER_DATA_DIR", "/opt/meta-ads-copilot-runtime/worker-data"))
    codex_home = Path(os.getenv("CODEX_HOME", str(worker_data / "codex")))
    allowed_roots = [worker_data / "hermes", worker_data / "artifacts", worker_data / "codex" / "uploads"]
    return codex_home / "auth.json", allowed_roots


def _call(name: str, arguments: dict) -> dict:
    auth_path, allowed_roots = _paths()
    if name == "codex_search":
        output = codex_capabilities.run_search(auth_path, **arguments)
        return _result(output)
    if name == "codex_vision":
        output = codex_capabilities.run_vision(
            auth_path,
            prompt=str(arguments["prompt"]),
            image_paths=list(arguments["image_paths"]),
            allowed_roots=allowed_roots,
            model=arguments.get("model"),
        )
        return _result(output)
    raise ValueError(f"Unknown tool: {name}")


def _handle(message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ads-meta-master-codex", "version": "0.1.0"},
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
            result = _call(str(params.get("name") or ""), dict(params.get("arguments") or {}))
        except (KeyError, ValueError, RuntimeError, OSError, httpx.HTTPError) as exc:
            result = _error(str(exc)[:2400])
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = _handle(message)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)[:1200]}},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
