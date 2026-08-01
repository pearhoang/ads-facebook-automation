from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_current_tenant_id, get_db, get_settings, require_owner, verify_csrf
from ..schemas import AIProviderConfigUpdateRequest, AIProviderConfigView
from ..services import ai_settings, auth


router = APIRouter(prefix="/api/ai-provider", tags=["ai-provider"])


@router.get("", response_model=AIProviderConfigView)
def get_provider_config(
    worker_id: str | None = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return ai_settings.serialize_config(ai_settings.get_config(db, tenant_id, worker_id))


@router.put("", response_model=AIProviderConfigView)
def save_provider_config(
    payload: AIProviderConfigUpdateRequest,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    config = ai_settings.upsert_config(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        provider_type=payload.provider_type,
        provider_name=payload.provider_name,
        base_url=payload.base_url,
        model=payload.model,
        thinking_mode=payload.thinking_mode,
        reasoning_effort=payload.reasoning_effort,
        agent_permission_mode=payload.agent_permission_mode,
        api_key=payload.api_key,
        execution_scope=payload.execution_scope,
        worker_id=payload.worker_id,
        encryption_key=settings.resolved_secret_encryption_key(),
    )
    return ai_settings.serialize_config(config)


@router.post("/test", response_model=AIProviderConfigView)
def test_provider_config(
    worker_id: str | None = Query(default=None),
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    config = ai_settings.test_config(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        encryption_key=settings.resolved_secret_encryption_key(),
        worker_id=worker_id,
    )
    return ai_settings.serialize_config(config)
