from __future__ import annotations

import os
import base64
import hashlib
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    database_url: str = "sqlite:///./data/app.db"
    worker_shared_secret: str = "change-me-before-running"
    dev_tenant_id: str | None = "00000000-0000-0000-0000-000000000001"
    browser_session_ttl_minutes: int = 20
    browser_proxy_port_min: int = 16080
    browser_proxy_port_max: int = 16179
    app_origin: str = "http://127.0.0.1:8000"
    session_cookie_name: str = "ads_lush_session"
    csrf_cookie_name: str = "ads_lush_csrf"
    session_ttl_hours: int = 168
    session_cookie_secure: bool = False
    artifact_root: str = "./data/execution-artifacts"
    artifact_max_bytes: int = 5 * 1024 * 1024
    creative_asset_root: str = "./data/creative-assets"
    creative_asset_max_bytes: int = 250 * 1024 * 1024
    secret_encryption_key: str = ""
    worker_bootstrap_repo_url: str = "https://github.com/pearhoang/ads-facebook-automation.git"
    worker_bootstrap_repo_branch: str = "main"
    worker_enrollment_ttl_minutes: int = 120
    hermes_dashboard_url: str = "https://hermes.ads.lushmedia.net"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "development").strip().lower(),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./data/app.db").strip(),
            worker_shared_secret=os.getenv("WORKER_SHARED_SECRET", "change-me-before-running"),
            dev_tenant_id=os.getenv("DEV_TENANT_ID") or None,
            browser_session_ttl_minutes=max(
                5,
                int(os.getenv("BROWSER_SESSION_TTL_MINUTES", "20")),
            ),
            browser_proxy_port_min=int(os.getenv("BROWSER_PROXY_PORT_MIN", "16080")),
            browser_proxy_port_max=int(os.getenv("BROWSER_PROXY_PORT_MAX", "16179")),
            app_origin=os.getenv("APP_ORIGIN", "http://127.0.0.1:8000").strip().rstrip("/"),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "ads_lush_session").strip(),
            csrf_cookie_name=os.getenv("CSRF_COOKIE_NAME", "ads_lush_csrf").strip(),
            session_ttl_hours=max(1, int(os.getenv("SESSION_TTL_HOURS", "168"))),
            session_cookie_secure=_env_bool(
                "SESSION_COOKIE_SECURE",
                os.getenv("APP_ENV", "development").strip().lower() == "production",
            ),
            artifact_root=os.getenv(
                "EXECUTION_ARTIFACT_ROOT", "./data/execution-artifacts"
            ).strip(),
            artifact_max_bytes=max(
                1024,
                int(os.getenv("EXECUTION_ARTIFACT_MAX_BYTES", str(5 * 1024 * 1024))),
            ),
            creative_asset_root=os.getenv(
                "CREATIVE_ASSET_ROOT", "./data/creative-assets"
            ).strip(),
            creative_asset_max_bytes=max(
                1024,
                int(
                    os.getenv(
                        "CREATIVE_ASSET_MAX_BYTES",
                        str(250 * 1024 * 1024),
                    )
                ),
            ),
            secret_encryption_key=os.getenv("SECRET_ENCRYPTION_KEY", "").strip(),
            worker_bootstrap_repo_url=os.getenv(
                "WORKER_BOOTSTRAP_REPO_URL",
                "https://github.com/pearhoang/ads-facebook-automation.git",
            ).strip(),
            worker_bootstrap_repo_branch=os.getenv(
                "WORKER_BOOTSTRAP_REPO_BRANCH", "main"
            ).strip()
            or "main",
            worker_enrollment_ttl_minutes=max(
                5,
                min(1440, int(os.getenv("WORKER_ENROLLMENT_TTL_MINUTES", "120"))),
            ),
            hermes_dashboard_url=os.getenv(
                "HERMES_DASHBOARD_URL",
                "https://hermes.ads.lushmedia.net",
            ).strip().rstrip("/"),
        )

    def resolved_secret_encryption_key(self) -> bytes:
        if self.secret_encryption_key:
            return self.secret_encryption_key.encode("ascii")
        digest = hashlib.sha256(self.worker_shared_secret.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def validate(self) -> None:
        if self.app_env == "production":
            if self.worker_shared_secret == "change-me-before-running":
                raise RuntimeError("WORKER_SHARED_SECRET must be changed in production.")
            if self.dev_tenant_id:
                raise RuntimeError("DEV_TENANT_ID must be disabled in production.")
            if not self.session_cookie_secure:
                raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production.")
            if not self.app_origin.startswith("https://"):
                raise RuntimeError("APP_ORIGIN must use HTTPS in production.")
            if not self.secret_encryption_key:
                raise RuntimeError("SECRET_ENCRYPTION_KEY must be configured in production.")
        if not self.session_cookie_name or not self.csrf_cookie_name:
            raise RuntimeError("Session and CSRF cookie names must not be empty.")
        if not self.artifact_root:
            raise RuntimeError("EXECUTION_ARTIFACT_ROOT must not be empty.")
        if not self.creative_asset_root:
            raise RuntimeError("CREATIVE_ASSET_ROOT must not be empty.")
        if self.app_env == "production" and not self.hermes_dashboard_url.startswith("https://"):
            raise RuntimeError("HERMES_DASHBOARD_URL must use HTTPS in production.")
        if not (1024 <= self.browser_proxy_port_min <= self.browser_proxy_port_max <= 65535):
            raise RuntimeError("Invalid browser proxy port range.")
