from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AdAccount,
    AuditEvent,
    CreativeAsset,
    ExecutionJob,
    MetaResource,
    new_id,
    utc_now,
)


RESOURCE_KINDS = {
    "page",
    "instagram_account",
    "dataset",
    "instant_form",
    "app",
}
RESOURCE_CONFIRMATION = "ĐÃ XÁC MINH TRÊN META"
ALLOWED_ASSET_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "video/mp4": {".mp4"},
    "video/quicktime": {".mov"},
}
RESOURCE_SELECTIONS = (
    ("targeting", "page_resource_id", "page", "page_name", "page_external_id"),
    (
        "targeting",
        "instagram_resource_id",
        "instagram_account",
        "instagram_account_name",
        "instagram_external_id",
    ),
    (
        "targeting",
        "dataset_resource_id",
        "dataset",
        "dataset_name",
        "dataset_external_id",
    ),
    ("targeting", "app_resource_id", "app", "app_name", "app_external_id"),
    (
        "creative",
        "lead_form_resource_id",
        "instant_form",
        "lead_form_name",
        "lead_form_external_id",
    ),
)


def _audit(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_type="user",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload,
        )
    )


def _get_ad_account(db: Session, tenant_id: str, ad_account_id: str) -> AdAccount:
    account = db.scalar(
        select(AdAccount).where(
            AdAccount.id == ad_account_id,
            AdAccount.tenant_id == tenant_id,
        )
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ad account.")
    return account


def get_resource(
    db: Session,
    tenant_id: str,
    resource_id: str,
    *,
    ad_account_id: str | None = None,
    expected_kind: str | None = None,
) -> MetaResource:
    clauses = [MetaResource.id == resource_id, MetaResource.tenant_id == tenant_id]
    if ad_account_id:
        clauses.append(MetaResource.ad_account_id == ad_account_id)
    if expected_kind:
        clauses.append(MetaResource.kind == expected_kind)
    resource = db.scalar(select(MetaResource).where(*clauses))
    if resource is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy Meta resource đúng loại trong ad account.",
        )
    return resource


def create_resource(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
    kind: str,
    label: str,
    external_id: str | None,
    metadata_json: dict,
) -> MetaResource:
    _get_ad_account(db, tenant_id, ad_account_id)
    if kind not in RESOURCE_KINDS:
        raise HTTPException(status_code=422, detail="Loại Meta resource không được hỗ trợ.")
    duplicate = db.scalar(
        select(MetaResource).where(
            MetaResource.ad_account_id == ad_account_id,
            MetaResource.kind == kind,
            MetaResource.label == label,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Resource cùng loại và tên đã tồn tại.")
    resource = MetaResource(
        tenant_id=tenant_id,
        ad_account_id=ad_account_id,
        kind=kind,
        label=label,
        external_id=external_id,
        status="unverified",
        metadata_json=metadata_json,
        created_by_user_id=user_id,
    )
    db.add(resource)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="meta_resource.created",
        entity_type="meta_resource",
        entity_id=resource.id,
        payload={"kind": kind, "label": label, "ad_account_id": ad_account_id},
    )
    db.commit()
    db.refresh(resource)
    return resource


def list_resources(
    db: Session,
    tenant_id: str,
    ad_account_id: str | None = None,
) -> list[MetaResource]:
    query = select(MetaResource).where(MetaResource.tenant_id == tenant_id)
    if ad_account_id:
        _get_ad_account(db, tenant_id, ad_account_id)
        query = query.where(MetaResource.ad_account_id == ad_account_id)
    return list(
        db.scalars(
            query.order_by(MetaResource.kind, MetaResource.label, MetaResource.created_at)
        )
    )


def verify_resource(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    resource_id: str,
    confirmation: str,
) -> MetaResource:
    if confirmation.strip() != RESOURCE_CONFIRMATION:
        raise HTTPException(
            status_code=422,
            detail=f"Hãy nhập chính xác: {RESOURCE_CONFIRMATION}",
        )
    resource = get_resource(db, tenant_id, resource_id)
    resource.status = "verified"
    resource.verified_by_user_id = user_id
    resource.verified_at = utc_now()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="meta_resource.verified",
        entity_type="meta_resource",
        entity_id=resource.id,
        payload={"kind": resource.kind, "label": resource.label},
    )
    db.commit()
    db.refresh(resource)
    return resource


def get_asset(
    db: Session,
    tenant_id: str,
    asset_id: str,
    *,
    ad_account_id: str | None = None,
) -> CreativeAsset:
    clauses = [CreativeAsset.id == asset_id, CreativeAsset.tenant_id == tenant_id]
    if ad_account_id:
        clauses.append(CreativeAsset.ad_account_id == ad_account_id)
    asset = db.scalar(select(CreativeAsset).where(*clauses))
    if asset is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy creative asset.")
    return asset


def list_assets(
    db: Session,
    tenant_id: str,
    ad_account_id: str | None = None,
) -> list[CreativeAsset]:
    query = select(CreativeAsset).where(CreativeAsset.tenant_id == tenant_id)
    if ad_account_id:
        _get_ad_account(db, tenant_id, ad_account_id)
        query = query.where(CreativeAsset.ad_account_id == ad_account_id)
    return list(db.scalars(query.order_by(CreativeAsset.created_at.desc())))


def _validate_asset_signature(content_type: str, first_bytes: bytes) -> bool:
    if content_type == "image/png":
        return first_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return first_bytes.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return first_bytes.startswith(b"RIFF") and first_bytes[8:12] == b"WEBP"
    if content_type in {"video/mp4", "video/quicktime"}:
        return len(first_bytes) >= 12 and first_bytes[4:8] == b"ftyp"
    return False


async def store_asset(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
    label: str,
    file_name: str,
    content_type: str,
    chunks: AsyncIterator[bytes],
    storage_root: str,
    max_bytes: int,
    allow_existing: bool = False,
    metadata_json: dict | None = None,
) -> CreativeAsset:
    _get_ad_account(db, tenant_id, ad_account_id)
    normalized_name = Path(file_name).name.strip()
    if not normalized_name or normalized_name in {".", ".."}:
        raise HTTPException(status_code=422, detail="Tên file creative không hợp lệ.")
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    allowed_suffixes = ALLOWED_ASSET_TYPES.get(normalized_type)
    suffix = Path(normalized_name).suffix.lower()
    if not allowed_suffixes or suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=415,
            detail="Chỉ hỗ trợ JPG, PNG, WEBP, MP4 hoặc MOV đúng Content-Type.",
        )

    root = Path(storage_root).resolve()
    target_dir = (root / tenant_id / ad_account_id).resolve()
    target_dir.relative_to(root)
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target_dir / f".{new_id()}.upload"
    target: Path | None = None
    digest = hashlib.sha256()
    byte_size = 0
    first_bytes = b""
    try:
        with temporary.open("xb") as handle:
            async for chunk in chunks:
                if not chunk:
                    continue
                byte_size += len(chunk)
                if byte_size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Creative asset vượt quá giới hạn dung lượng.",
                    )
                if len(first_bytes) < 32:
                    first_bytes += chunk[: 32 - len(first_bytes)]
                digest.update(chunk)
                handle.write(chunk)
        if byte_size == 0:
            raise HTTPException(status_code=422, detail="Creative asset rỗng.")
        if not _validate_asset_signature(normalized_type, first_bytes):
            raise HTTPException(
                status_code=415,
                detail="Nội dung file không khớp Content-Type đã khai báo.",
            )
        sha256 = digest.hexdigest()
        duplicate = db.scalar(
            select(CreativeAsset).where(
                CreativeAsset.ad_account_id == ad_account_id,
                CreativeAsset.sha256 == sha256,
            )
        )
        if duplicate is not None:
            if allow_existing:
                temporary.unlink(missing_ok=True)
                return duplicate
            raise HTTPException(status_code=409, detail=f"Asset trùng nội dung với '{duplicate.label}'.")
        asset_id = new_id()
        target = (target_dir / f"{asset_id}{suffix}").resolve()
        target.relative_to(root)
        os.replace(temporary, target)
        asset = CreativeAsset(
            id=asset_id,
            tenant_id=tenant_id,
            ad_account_id=ad_account_id,
            label=label.strip(),
            file_name=normalized_name,
            content_type=normalized_type,
            byte_size=byte_size,
            sha256=sha256,
            storage_path=str(target),
            status="ready",
            metadata_json={"extension": suffix, **(metadata_json or {})},
            created_by_user_id=user_id,
        )
        db.add(asset)
        db.flush()
        _audit(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="creative_asset.created",
            entity_type="creative_asset",
            entity_id=asset.id,
            payload={
                "label": asset.label,
                "file_name": asset.file_name,
                "byte_size": asset.byte_size,
                "sha256": asset.sha256,
            },
        )
        db.commit()
        db.refresh(asset)
        return asset
    except Exception:
        temporary.unlink(missing_ok=True)
        if target is not None:
            target.unlink(missing_ok=True)
        raise


def resolve_campaign_inputs(
    db: Session,
    *,
    tenant_id: str,
    ad_account_id: str,
    targeting_json: dict,
    creative_json: dict,
) -> tuple[dict, dict]:
    targeting = dict(targeting_json or {})
    creative = dict(creative_json or {})
    roots = {"targeting": targeting, "creative": creative}
    for root_name, id_key, kind, label_key, external_key in RESOURCE_SELECTIONS:
        target = roots[root_name]
        resource_id = str(target.get(id_key) or "").strip()
        if not resource_id:
            continue
        resource = get_resource(
            db,
            tenant_id,
            resource_id,
            ad_account_id=ad_account_id,
            expected_kind=kind,
        )
        target[label_key] = resource.label
        target[external_key] = resource.external_id or ""
        target[f"{id_key.removesuffix('_id')}_status"] = resource.status

    asset_id = str(creative.get("asset_id") or "").strip()
    if asset_id:
        asset = get_asset(
            db,
            tenant_id,
            asset_id,
            ad_account_id=ad_account_id,
        )
        if asset.status != "ready" or not Path(asset.storage_path).is_file():
            raise HTTPException(status_code=409, detail="Creative asset chưa sẵn sàng.")
        creative["asset_snapshot"] = {
            "id": asset.id,
            "label": asset.label,
            "file_name": asset.file_name,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "sha256": asset.sha256,
        }
    return targeting, creative


def execution_resource_findings(
    db: Session,
    *,
    tenant_id: str,
    ad_account_id: str,
    targeting: dict,
    creative: dict,
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    roots = {"targeting": targeting, "creative": creative}
    for root_name, id_key, kind, _, _ in RESOURCE_SELECTIONS:
        target = roots[root_name]
        resource_id = str(target.get(id_key) or "").strip()
        if not resource_id:
            continue
        try:
            resource = get_resource(
                db,
                tenant_id,
                resource_id,
                ad_account_id=ad_account_id,
                expected_kind=kind,
            )
        except HTTPException:
            blockers.append(f"Resource {kind} trong snapshot không còn hợp lệ.")
            continue
        if resource.status != "verified":
            blockers.append(
                f"Resource '{resource.label}' ({kind}) chưa được xác minh trên Meta."
            )

    asset_id = str(creative.get("asset_id") or "").strip()
    if asset_id:
        try:
            asset = get_asset(
                db,
                tenant_id,
                asset_id,
                ad_account_id=ad_account_id,
            )
        except HTTPException:
            blockers.append("Creative asset trong snapshot không còn tồn tại.")
        else:
            snapshot = creative.get("asset_snapshot") or {}
            if asset.status != "ready" or not Path(asset.storage_path).is_file():
                blockers.append(f"Creative asset '{asset.label}' chưa sẵn sàng.")
            elif snapshot.get("sha256") != asset.sha256:
                blockers.append(f"Creative asset '{asset.label}' không khớp digest đã duyệt.")
    return blockers, warnings


def get_worker_job_asset(
    db: Session,
    *,
    worker_id: str,
    job_id: str,
    asset_id: str,
) -> CreativeAsset:
    job = db.scalar(
        select(ExecutionJob).where(
            ExecutionJob.id == job_id,
            ExecutionJob.worker_id == worker_id,
            ExecutionJob.status.in_({"claimed", "running"}),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Active execution job not found.")
    creative = (job.payload_json.get("draft_spec") or {}).get("creative") or {}
    snapshot = creative.get("asset_snapshot") or {}
    if str(creative.get("asset_id") or snapshot.get("id") or "") != asset_id:
        raise HTTPException(status_code=403, detail="Asset is not referenced by this job.")
    asset = get_asset(
        db,
        job.tenant_id,
        asset_id,
        ad_account_id=job.ad_account_id,
    )
    if asset.sha256 != snapshot.get("sha256") or not Path(asset.storage_path).is_file():
        raise HTTPException(status_code=409, detail="Asset digest or storage state changed.")
    return asset


def validate_facebook_launch_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "facebook.com" or host.endswith(".facebook.com")
    ):
        raise HTTPException(status_code=422, detail="launch_url phải là HTTPS Facebook URL.")
    if "adsmanager" not in parsed.path.lower():
        raise HTTPException(status_code=422, detail="launch_url phải trỏ tới Ads Manager.")
    return normalized
