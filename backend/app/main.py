from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import ai, auth, bot_nodes, campaigns, execution, reports, user, worker
from .config import Settings
from .db import Database
from .schemas import HealthView
from . import web


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    app_settings.validate()
    database = Database(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app_settings.app_env != "production":
            database.create_schema()
        yield
        database.engine.dispose()

    app = FastAPI(
        title="Meta Ads Copilot",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if app_settings.app_env == "production" else "/docs",
        redoc_url=None if app_settings.app_env == "production" else "/redoc",
        openapi_url=None if app_settings.app_env == "production" else "/openapi.json",
    )
    app.state.settings = app_settings
    app.state.database = database
    app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")
    app.include_router(web.router)
    app.include_router(auth.router)
    app.include_router(campaigns.router)
    app.include_router(execution.router)
    app.include_router(reports.router)
    app.include_router(user.router)
    app.include_router(bot_nodes.router)
    app.include_router(ai.router)
    app.include_router(worker.router)

    @app.get("/health", response_model=HealthView, tags=["system"])
    def health() -> HealthView:
        return HealthView(status="ok")

    return app


app = create_app()
