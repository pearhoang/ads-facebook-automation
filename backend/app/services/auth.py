from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Tenant, TenantMembership, User, UserSession, utc_now


password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("meta-ads-copilot-dummy-password")


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    session_id: str
    user_id: str
    email: str
    display_name: str
    tenant_id: str
    tenant_name: str
    role: str
    csrf_token_hash: str


@dataclass(frozen=True, slots=True)
class IssuedSession:
    principal: AuthPrincipal
    session_token: str
    csrf_token: str
    expires_at: datetime


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _not_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value > utc_now()


def provision_admin(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    email: str,
    display_name: str,
    password: str,
) -> User:
    normalized_email = normalize_email(email)
    if len(password) < 12:
        raise ValueError("Admin password must contain at least 12 characters.")

    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(id=tenant_id, name=tenant_name.strip())
        db.add(tenant)
    else:
        tenant.name = tenant_name.strip()

    user = db.scalar(select(User).where(User.normalized_email == normalized_email))
    if user is None:
        user = User(
            email=email.strip(),
            normalized_email=normalized_email,
            display_name=display_name.strip(),
            password_hash=password_hash.hash(password),
            status="active",
        )
        db.add(user)
        db.flush()
    else:
        user.email = email.strip()
        user.display_name = display_name.strip()
        user.password_hash = password_hash.hash(password)
        user.status = "active"

    membership = db.get(
        TenantMembership,
        {"user_id": user.id, "tenant_id": tenant_id},
    )
    if membership is None:
        db.add(TenantMembership(user_id=user.id, tenant_id=tenant_id, role="owner"))
    else:
        membership.role = "owner"
    db.commit()
    db.refresh(user)
    return user


def authenticate(
    db: Session,
    *,
    email: str,
    password: str,
    ttl_hours: int,
    tenant_id: str | None = None,
) -> IssuedSession:
    user = db.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    candidate_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_valid = password_hash.verify(password, candidate_hash)
    if user is None or not password_valid or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    membership_query = select(TenantMembership, Tenant).join(
        Tenant, Tenant.id == TenantMembership.tenant_id
    ).where(TenantMembership.user_id == user.id)
    if tenant_id:
        membership_query = membership_query.where(TenantMembership.tenant_id == tenant_id)
    memberships = list(db.execute(membership_query).all())
    if not memberships:
        raise HTTPException(status_code=403, detail="Tài khoản chưa được cấp workspace.")
    if len(memberships) > 1 and not tenant_id:
        raise HTTPException(status_code=409, detail="Hãy chọn workspace để tiếp tục.")

    membership, tenant = memberships[0]
    raw_session_token = secrets.token_urlsafe(48)
    raw_csrf_token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(hours=ttl_hours)
    user_session = UserSession(
        token_hash=token_digest(raw_session_token),
        csrf_token_hash=token_digest(raw_csrf_token),
        user_id=user.id,
        tenant_id=tenant.id,
        expires_at=expires_at,
    )
    user.last_login_at = utc_now()
    db.add(user_session)
    db.commit()
    db.refresh(user_session)
    return IssuedSession(
        principal=AuthPrincipal(
            session_id=user_session.id,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            role=membership.role,
            csrf_token_hash=user_session.csrf_token_hash,
        ),
        session_token=raw_session_token,
        csrf_token=raw_csrf_token,
        expires_at=expires_at,
    )


def load_principal(db: Session, raw_session_token: str | None) -> AuthPrincipal | None:
    if not raw_session_token:
        return None
    row = db.execute(
        select(UserSession, User, TenantMembership, Tenant)
        .join(User, User.id == UserSession.user_id)
        .join(
            TenantMembership,
            (TenantMembership.user_id == UserSession.user_id)
            & (TenantMembership.tenant_id == UserSession.tenant_id),
        )
        .join(Tenant, Tenant.id == UserSession.tenant_id)
        .where(UserSession.token_hash == token_digest(raw_session_token))
    ).one_or_none()
    if row is None:
        return None
    user_session, user, membership, tenant = row
    if user_session.revoked_at is not None or not _not_expired(user_session.expires_at):
        return None
    if user.status != "active":
        return None
    return AuthPrincipal(
        session_id=user_session.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        role=membership.role,
        csrf_token_hash=user_session.csrf_token_hash,
    )


def verify_csrf_token(principal: AuthPrincipal, cookie_token: str | None, header_token: str | None) -> None:
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token không hợp lệ.")
    if not secrets.compare_digest(token_digest(cookie_token), principal.csrf_token_hash):
        raise HTTPException(status_code=403, detail="CSRF token không hợp lệ.")


def revoke_session(db: Session, session_id: str) -> None:
    user_session = db.get(UserSession, session_id)
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = utc_now()
        db.commit()
