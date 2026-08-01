from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..dependencies import get_current_principal, get_db, verify_csrf
from ..schemas import (
    AgentConversationCreateRequest,
    AgentConversationView,
    AgentJobView,
    AgentMessageCreateRequest,
    AgentMessageView,
    AgentSyncRequest,
)
from ..services import agent_chat, auth


router = APIRouter(prefix="/api/ai-copilot", tags=["ai-copilot"])


@router.get("/conversations", response_model=list[AgentConversationView])
def list_conversations(
    worker_id: str | None = Query(default=None, max_length=36),
    profile: str | None = Query(default=None, pattern=r"^ads$"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    return agent_chat.list_conversations(
        db,
        tenant_id=principal.tenant_id,
        role=principal.role,
        worker_id=worker_id,
        profile=profile,
        limit=limit,
    )


@router.post(
    "/conversations",
    response_model=AgentConversationView,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: AgentConversationCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return agent_chat.create_conversation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        **payload.model_dump(),
    )


@router.post("/sync", response_model=AgentJobView, status_code=status.HTTP_202_ACCEPTED)
def sync_sessions(
    payload: AgentSyncRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return agent_chat.queue_session_sync(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        **payload.model_dump(),
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[AgentMessageView],
)
def list_messages(
    conversation_id: str,
    limit: int = Query(default=300, ge=1, le=500),
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    return agent_chat.list_messages(
        db,
        tenant_id=principal.tenant_id,
        conversation_id=conversation_id,
        role=principal.role,
        limit=limit,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AgentJobView,
    status_code=status.HTTP_202_ACCEPTED,
)
def send_message(
    conversation_id: str,
    payload: AgentMessageCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return agent_chat.queue_chat_turn(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        conversation_id=conversation_id,
        content=payload.content,
        attachments=[item.model_dump() for item in payload.attachments],
    )


@router.get("/jobs/{job_id}", response_model=AgentJobView)
def get_job(
    job_id: str,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    return agent_chat.get_job(
        db, tenant_id=principal.tenant_id, job_id=job_id, role=principal.role
    )
