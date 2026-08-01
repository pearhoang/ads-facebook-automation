from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .models import BrowserSession
from .dependencies import get_db, resolve_optional_principal
from .services import auth


router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="backend/app/templates")
ACTIVE_PROXY_STATES = {"starting", "awaiting_user", "ready", "closing"}


@router.get("/", response_class=HTMLResponse)
def workspace(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="workspace.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if resolve_optional_principal(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/campaigns", response_class=HTMLResponse)
def campaigns_page(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="campaigns.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/bot-nodes", response_class=HTMLResponse)
def bot_nodes_page(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="bot_nodes.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
            "default_repo_url": settings.worker_bootstrap_repo_url,
            "default_repo_branch": settings.worker_bootstrap_repo_branch,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/ai-copilot", response_class=HTMLResponse)
def ai_copilot_page(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="ai_copilot.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/hermes-agents", response_class=HTMLResponse)
def hermes_agents_page(request: Request, db: Session = Depends(get_db)):
    principal = resolve_optional_principal(request, db)
    if principal is None:
        return RedirectResponse("/login", status_code=303)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="hermes_agents.html",
        context={
            "principal": principal,
            "csrf_token": request.cookies.get(settings.csrf_cookie_name, ""),
        },
        headers={"Cache-Control": "no-store"},
    )


def _load_proxy_target(request: Request, session_id: str) -> BrowserSession:
    settings = request.app.state.settings
    with request.app.state.database.session_factory() as db:
        principal = auth.load_principal(
            db,
            request.cookies.get(settings.session_cookie_name),
        )
        if principal is None:
            raise HTTPException(status_code=401, detail="Bạn chưa đăng nhập.")
        browser_session = db.scalar(
            select(BrowserSession).where(
                BrowserSession.id == session_id,
                BrowserSession.tenant_id == principal.tenant_id,
            )
        )
        if browser_session is None or browser_session.status not in ACTIVE_PROXY_STATES:
            raise HTTPException(status_code=404, detail="Browser session is not available.")
        if browser_session.web_port is None or not (
            settings.browser_proxy_port_min
            <= browser_session.web_port
            <= settings.browser_proxy_port_max
        ):
            raise HTTPException(status_code=409, detail="Browser session proxy is not ready.")
        db.expunge(browser_session)
        return browser_session


@router.get("/browser/{session_id}/{asset_path:path}")
async def browser_http_proxy(request: Request, session_id: str, asset_path: str):
    if not asset_path or any(part in {"..", ""} for part in asset_path.split("/")):
        raise HTTPException(status_code=400, detail="Invalid browser asset path.")
    browser_session = _load_proxy_target(request, session_id)
    upstream_url = f"http://127.0.0.1:{browser_session.web_port}/{asset_path}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        upstream = await client.get(upstream_url, params=request.query_params)
    excluded = {"content-length", "connection", "transfer-encoding", "content-encoding"}
    headers = {key: value for key, value in upstream.headers.items() if key.lower() not in excluded}
    headers["Cache-Control"] = "no-store"
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)


@router.websocket("/browser/{session_id}/websockify")
async def browser_websocket_proxy(websocket: WebSocket, session_id: str):
    settings = websocket.app.state.settings
    if settings.app_env == "production" and websocket.headers.get("origin") != settings.app_origin:
        await websocket.close(code=4403, reason="Origin is not allowed.")
        return
    try:
        browser_session = _load_proxy_target(websocket, session_id)
    except HTTPException as exc:
        await websocket.close(code=4401 if exc.status_code == 401 else 4404, reason=str(exc.detail))
        return

    offered = websocket.headers.get("sec-websocket-protocol", "")
    subprotocols = [item.strip() for item in offered.split(",") if item.strip()]
    selected = "binary" if "binary" in subprotocols else (subprotocols[0] if subprotocols else None)
    await websocket.accept(subprotocol=selected)

    try:
        async with connect(
            f"ws://127.0.0.1:{browser_session.web_port}/websockify",
            subprotocols=[selected] if selected else None,
            max_size=None,
        ) as upstream:

            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream.send(message["text"])

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = {
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except (WebSocketDisconnect, ConnectionClosed, OSError):
        return
