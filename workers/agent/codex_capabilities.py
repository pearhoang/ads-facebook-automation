from __future__ import annotations

import base64
import json
import os
import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

# OAuth/search request shape adapted from pearhoang/pi-setup codex-search.ts
# (Apache-2.0). This is a Python Hermes adapter, not a Pi runtime.
# Source: https://github.com/pearhoang/pi-setup/blob/main/extensions/codex-search.ts

DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api"
DEFAULT_REFRESH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CHATGPT_AUTH_CLAIM = "https://api.openai.com/auth"
DEFAULT_SEARCH_MODEL = "gpt-5.4-mini"
DEFAULT_VISION_MODEL = "gpt-5.4-mini"
ACCESS_TOKEN_REFRESH_WINDOW_SECONDS = 300
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 8
MAX_TOOL_OUTPUT_BYTES = 128 * 1024
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass(frozen=True, slots=True)
class CodexCredential:
    access_token: str
    account_id: str
    refresh_token: str | None = None
    email: str | None = None
    plan_type: str | None = None
    expires_at: int | None = None


def _decode_jwt(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _token_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        raw = value.get("raw_jwt")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _credential_from_json(payload: dict[str, Any]) -> CodexCredential | None:
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        return None
    access_token = _token_value(tokens.get("access_token"))
    if not access_token:
        return None
    refresh_token = _token_value(tokens.get("refresh_token"))
    id_token = _token_value(tokens.get("id_token"))
    access_payload = _decode_jwt(access_token)
    id_payload = _decode_jwt(id_token)
    access_claim = access_payload.get(CHATGPT_AUTH_CLAIM)
    id_claim = id_payload.get(CHATGPT_AUTH_CLAIM)
    access_claim = access_claim if isinstance(access_claim, dict) else {}
    id_claim = id_claim if isinstance(id_claim, dict) else {}
    account_id = (
        tokens.get("account_id")
        or access_claim.get("chatgpt_account_id")
        or id_claim.get("chatgpt_account_id")
    )
    if not isinstance(account_id, str) or not account_id.strip():
        return None
    expires = access_payload.get("exp")
    expires_at = int(expires) if isinstance(expires, (int, float)) else None
    email = id_claim.get("email") or id_payload.get("email")
    plan_type = id_claim.get("chatgpt_plan_type") or access_claim.get("chatgpt_plan_type")
    return CodexCredential(
        access_token=access_token,
        account_id=account_id.strip(),
        refresh_token=refresh_token,
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        plan_type=plan_type.strip() if isinstance(plan_type, str) and plan_type.strip() else None,
        expires_at=expires_at,
    )


def _read_auth(auth_path: Path) -> tuple[dict[str, Any], CodexCredential] | None:
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    credential = _credential_from_json(payload)
    return (payload, credential) if credential else None


def capability_status(auth_path: Path) -> dict[str, Any]:
    loaded = _read_auth(auth_path)
    if loaded is None:
        return {"configured": False}
    _, credential = loaded
    return {
        "configured": True,
        "account_id": credential.account_id,
        "email": credential.email,
        "plan_type": credential.plan_type,
        "refreshable": bool(credential.refresh_token),
    }


def _write_auth_atomic(auth_path: Path, payload: dict[str, Any]) -> None:
    auth_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = auth_path.with_name(f".{auth_path.name}.{secrets.token_hex(6)}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, auth_path)


def load_credential(auth_path: Path, *, allow_refresh: bool = True) -> CodexCredential:
    loaded = _read_auth(auth_path)
    if loaded is None:
        raise RuntimeError("Chưa kết nối Codex. Mở Hermes Agents và chọn Kết nối Codex trước.")
    payload, credential = loaded
    fresh = credential.expires_at is None or credential.expires_at > time.time() + ACCESS_TOKEN_REFRESH_WINDOW_SECONDS
    if fresh or not allow_refresh:
        return credential
    if not credential.refresh_token:
        raise RuntimeError("Codex OAuth đã hết hạn và không có refresh token. Hãy kết nối Codex lại.")
    with httpx.Client(timeout=60) as client:
        response = client.post(
            os.getenv("CODEX_REFRESH_TOKEN_URL_OVERRIDE", DEFAULT_REFRESH_TOKEN_URL),
            json={
                "client_id": CODEX_OAUTH_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": credential.refresh_token,
            },
        )
        response.raise_for_status()
        refreshed = response.json()
    tokens = payload.setdefault("tokens", {})
    if not isinstance(tokens, dict):
        raise RuntimeError("Codex auth.json có trường tokens không hợp lệ.")
    for source, target in (
        ("access_token", "access_token"),
        ("refresh_token", "refresh_token"),
        ("id_token", "id_token"),
    ):
        value = refreshed.get(source)
        if isinstance(value, str) and value:
            tokens[target] = value
    payload["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_auth_atomic(auth_path, payload)
    reloaded = _read_auth(auth_path)
    if reloaded is None:
        raise RuntimeError("Đã refresh Codex OAuth nhưng không đọc lại được credential.")
    return reloaded[1]


def _clean_domains(domains: list[str] | None) -> list[str] | None:
    if not domains:
        return None
    cleaned: list[str] = []
    for value in domains:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        domain = (parsed.hostname or "").lower().strip(".")
        if domain and re.fullmatch(r"[a-z0-9.-]+", domain) and domain not in cleaned:
            cleaned.append(domain)
    return cleaned or None


def build_search_request(
    *,
    query: str,
    model: str | None = None,
    recency_days: int | None = None,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    context_size: str = "medium",
    response_length: str = "medium",
    include_image_results: bool = False,
) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise ValueError("query không được để trống.")
    if context_size not in {"low", "medium", "high"}:
        raise ValueError("context_size phải là low, medium hoặc high.")
    if response_length not in {"short", "medium", "long"}:
        raise ValueError("response_length phải là short, medium hoặc long.")
    if recency_days is not None and (not isinstance(recency_days, int) or recency_days <= 0):
        raise ValueError("recency_days phải là số nguyên dương.")
    allowed = _clean_domains(allowed_domains)
    blocked = _clean_domains(blocked_domains)
    search_query: dict[str, Any] = {"q": query}
    if recency_days is not None:
        search_query["recency"] = recency_days
    if allowed:
        search_query["domains"] = allowed
    commands: dict[str, Any] = {
        "search_query": [search_query],
        "response_length": response_length,
    }
    settings: dict[str, Any] = {
        "search_context_size": context_size,
        "allowed_callers": ["direct"],
        "external_web_access": "live",
    }
    if allowed or blocked:
        settings["filters"] = {
            **({"allowed_domains": allowed} if allowed else {}),
            **({"blocked_domains": blocked} if blocked else {}),
        }
    if include_image_results:
        settings["image_settings"] = {"max_results": 4, "caption": True}
        commands["image_query"] = [search_query]
    return {
        "id": f"ads-codex-search-{int(time.time() * 1000)}-{secrets.token_hex(4)}",
        "model": (model or DEFAULT_SEARCH_MODEL).strip(),
        "input": query,
        "commands": commands,
        "settings": settings,
    }


def run_search(auth_path: Path, **arguments: Any) -> str:
    credential = load_credential(auth_path)
    payload = build_search_request(**arguments)
    base_url = os.getenv("CODEX_BACKEND_BASE_URL", DEFAULT_CODEX_BASE_URL).rstrip("/")
    url = f"{base_url}/alpha/search" if base_url.endswith("/codex") else f"{base_url}/codex/alpha/search"
    with httpx.Client(timeout=90) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {credential.access_token}",
                "ChatGPT-Account-ID": credential.account_id,
                "originator": "ads-meta-master-codex-capability",
                "User-Agent": "ads-meta-master-codex-capability/0.1",
            },
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
    output = result.get("output") if isinstance(result, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise RuntimeError("Codex search không trả về nội dung text.")
    return output[:MAX_TOOL_OUTPUT_BYTES]


def validate_image_paths(paths: list[str], *, allowed_roots: list[Path]) -> list[Path]:
    if not paths or len(paths) > MAX_IMAGES:
        raise ValueError(f"codex_vision cần từ 1 đến {MAX_IMAGES} ảnh.")
    roots = [root.resolve() for root in allowed_roots]
    validated: list[Path] = []
    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not any(candidate.is_relative_to(root) for root in roots):
            raise ValueError(f"Ảnh nằm ngoài vùng dữ liệu được phép: {candidate}")
        if not candidate.is_file():
            raise ValueError(f"Không tìm thấy ảnh: {candidate}")
        if candidate.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"Định dạng ảnh không được hỗ trợ: {candidate.suffix}")
        if candidate.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError(f"Ảnh vượt quá giới hạn {MAX_IMAGE_BYTES // (1024 * 1024)} MB: {candidate.name}")
        validated.append(candidate)
    return validated


def run_vision(
    auth_path: Path,
    *,
    prompt: str,
    image_paths: list[str],
    allowed_roots: list[Path],
    model: str | None = None,
) -> str:
    load_credential(auth_path)
    images = validate_image_paths(image_paths, allowed_roots=allowed_roots)
    codex_home = auth_path.parent
    output_dir = codex_home / "outputs"
    work_dir = codex_home / "work"
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_path = output_dir / f"vision-{secrets.token_hex(8)}.txt"
    command = [
        os.getenv("CODEX_BIN", "codex"),
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--cd",
        str(work_dir),
        "--model",
        (model or DEFAULT_VISION_MODEL).strip(),
        "--output-last-message",
        str(output_path),
    ]
    for image in images:
        command.extend(["--image", str(image)])
    command.append("-")
    env = {**os.environ, "CODEX_HOME": str(codex_home)}
    try:
        completed = subprocess.run(
            command,
            input=(prompt.strip() or "Mô tả chính xác nội dung ảnh.") + "\n",
            text=True,
            capture_output=True,
            timeout=240,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()[-12:]
            raise RuntimeError("\n".join(detail)[-2000:] or "Codex vision thất bại.")
        if not output_path.is_file():
            raise RuntimeError("Codex vision không tạo kết quả cuối.")
        output = output_path.read_text(encoding="utf-8").strip()
        if not output:
            raise RuntimeError("Codex vision trả về nội dung rỗng.")
        return output[:MAX_TOOL_OUTPUT_BYTES]
    finally:
        output_path.unlink(missing_ok=True)
