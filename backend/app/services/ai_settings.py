from __future__ import annotations

from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AIProviderConfig, AuditEvent, WorkerTenantAssignment, utc_now


def _cipher(key: bytes) -> Fernet:
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY phải là Fernet key hợp lệ.") from exc


def _encrypt(key: bytes, value: str) -> str:
    return _cipher(key).encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(key: bytes, value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _cipher(key).decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Không giải mã được AI API key bằng key hiện tại.") from exc


def _key_hint(value: str) -> str:
    normalized = value.strip()
    if len(normalized) <= 8:
        return normalized[-2:]
    return normalized[-6:]


def _masked(hint: str | None) -> str | None:
    return f"••••••••{hint}" if hint else None


def _audit(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    action: str,
    entity_id: str,
    payload: dict,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_type="user",
            action=action,
            entity_type="ai_provider_config",
            entity_id=entity_id,
            payload_json=payload,
        )
    )


def get_config(
    db: Session,
    tenant_id: str,
    worker_id: str | None = None,
) -> AIProviderConfig | None:
    return db.scalar(
        select(AIProviderConfig)
        .where(
            AIProviderConfig.tenant_id == tenant_id,
            AIProviderConfig.worker_id == worker_id,
        )
        .order_by(AIProviderConfig.updated_at.desc())
    )


def serialize_config(config: AIProviderConfig | None) -> dict:
    if config is None:
        return {"configured": False}
    return {
        "configured": True,
        "provider_type": config.provider_type,
        "provider_name": config.provider_name,
        "base_url": config.base_url,
        "model": config.model,
        "api_key_masked": _masked(config.api_key_hint),
        "execution_scope": config.execution_scope,
        "worker_id": config.worker_id,
        "status": config.status,
        "last_test_status": config.last_test_status,
        "last_test_error": config.last_test_error,
        "last_tested_at": config.last_tested_at,
        "updated_at": config.updated_at,
    }


def upsert_config(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    provider_type: str,
    provider_name: str,
    base_url: str,
    model: str,
    api_key: str | None,
    execution_scope: str,
    worker_id: str | None,
    encryption_key: bytes,
) -> AIProviderConfig:
    if worker_id is not None:
        assignment = db.get(
            WorkerTenantAssignment,
            {"worker_id": worker_id, "tenant_id": tenant_id},
        )
        if assignment is None:
            raise HTTPException(status_code=404, detail="Bot VPS không thuộc workspace.")
    config = get_config(db, tenant_id, worker_id)
    is_new = config is None
    if config is None:
        config = AIProviderConfig(
            tenant_id=tenant_id,
            base_url=base_url,
            model=model,
            updated_by_user_id=user_id,
        )
        db.add(config)
    if api_key is not None and api_key.strip():
        normalized_key = api_key.strip()
        config.api_key_ciphertext = _encrypt(encryption_key, normalized_key)
        config.api_key_hint = _key_hint(normalized_key)
    elif config.api_key_ciphertext is None and not base_url.startswith(
        ("http://127.0.0.1", "http://localhost")
    ):
        raise HTTPException(status_code=422, detail="API key là bắt buộc cho endpoint từ xa.")
    config.provider_type = provider_type
    config.provider_name = provider_name
    config.base_url = base_url
    config.model = model
    config.execution_scope = execution_scope
    config.worker_id = worker_id
    config.status = "configured"
    config.last_test_status = None
    config.last_test_error = None
    config.updated_by_user_id = user_id
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="Đã cấu hình AI provider" if is_new else "Đã cập nhật AI provider",
        entity_id=config.id,
        payload={
            "provider_name": provider_name,
            "base_url_host": urlparse(base_url).netloc,
            "model": model,
            "execution_scope": execution_scope,
            "worker_id": worker_id,
            "api_key_changed": bool(api_key and api_key.strip()),
        },
    )
    db.commit()
    db.refresh(config)
    return config


def runtime_config_for_worker(
    db: Session,
    *,
    worker_id: str,
    encryption_key: bytes,
) -> dict | None:
    config = db.scalar(
        select(AIProviderConfig).where(
            AIProviderConfig.worker_id == worker_id,
            AIProviderConfig.execution_scope == "worker",
            AIProviderConfig.status == "configured",
        )
    )
    if config is None:
        return None
    return {
        "provider_type": config.provider_type,
        "provider_name": config.provider_name,
        "base_url": config.base_url,
        "model": config.model,
        "api_key": _decrypt(encryption_key, config.api_key_ciphertext),
    }


def test_config(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    encryption_key: bytes,
    worker_id: str | None,
) -> AIProviderConfig:
    config = get_config(db, tenant_id, worker_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Chưa cấu hình AI provider.")
    if config.execution_scope == "worker":
        config.last_test_status = "pending_worker"
        config.last_test_error = "Worker sẽ xác minh endpoint khi nhận cấu hình runtime."
    else:
        api_key = _decrypt(encryption_key, config.api_key_ciphertext)
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        endpoint = f"{config.base_url.rstrip('/')}/models"
        try:
            response = httpx.get(endpoint, headers=headers, timeout=15, follow_redirects=False)
            response.raise_for_status()
            config.last_test_status = "passed"
            config.last_test_error = None
        except (httpx.HTTPError, RuntimeError) as exc:
            config.last_test_status = "failed"
            config.last_test_error = str(exc)[:1000]
    config.last_tested_at = utc_now()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="Đã kiểm tra AI provider",
        entity_id=config.id,
        payload={"status": config.last_test_status},
    )
    db.commit()
    db.refresh(config)
    return config
