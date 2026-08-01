from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrowserSessionAssignment:
    session_id: str
    account_id: str
    profile_key: str
    status: str
    expires_at: str
    launch_url: str | None = None
    novnc_url: str | None = None
    web_port: int | None = None

    @classmethod
    def from_payload(cls, payload: dict) -> "BrowserSessionAssignment":
        return cls(
            session_id=str(payload["id"]),
            account_id=str(payload["account_id"]),
            profile_key=str(payload["profile_key"]),
            status=str(payload["status"]),
            expires_at=str(payload["expires_at"]),
            launch_url=payload.get("launch_url"),
            novnc_url=payload.get("novnc_url"),
            web_port=payload.get("web_port"),
        )


class BrowserRuntime:
    """Boundary implemented by fake runtime in tests and Linux noVNC runtime in production."""

    def launch(self, record: dict) -> dict:
        raise NotImplementedError

    def stop(self, record: dict) -> None:
        raise NotImplementedError

    def is_running(self, record: dict) -> bool:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ExecutionJobAssignment:
    job_id: str
    campaign_draft_id: str
    facebook_account_id: str
    profile_key: str
    meta_ad_account_id: str
    status: str
    payload: dict

    @classmethod
    def from_payload(cls, payload: dict) -> "ExecutionJobAssignment":
        return cls(
            job_id=str(payload["id"]),
            campaign_draft_id=str(payload["campaign_draft_id"]),
            facebook_account_id=str(payload["facebook_account_id"]),
            profile_key=str(payload["profile_key"]),
            meta_ad_account_id=str(payload["meta_ad_account_id"]),
            status=str(payload["status"]),
            payload=dict(payload.get("payload_json") or {}),
        )


@dataclass(frozen=True, slots=True)
class ReportJobAssignment:
    job_id: str
    facebook_account_id: str
    profile_key: str
    meta_ad_account_id: str
    ad_account_label: str
    currency: str
    status: str
    range_start: str
    range_end: str
    payload: dict

    @classmethod
    def from_payload(cls, payload: dict) -> "ReportJobAssignment":
        return cls(
            job_id=str(payload["id"]),
            facebook_account_id=str(payload["facebook_account_id"]),
            profile_key=str(payload["profile_key"]),
            meta_ad_account_id=str(payload["meta_ad_account_id"]),
            ad_account_label=str(payload["ad_account_label"]),
            currency=str(payload["currency"]),
            status=str(payload["status"]),
            range_start=str(payload["range_start"]),
            range_end=str(payload["range_end"]),
            payload=dict(payload.get("payload_json") or {}),
        )


@dataclass(frozen=True, slots=True)
class AgentJobAssignment:
    job_id: str
    conversation_id: str | None
    profile: str
    job_type: str
    status: str
    hermes_session_id: str | None
    payload: dict

    @classmethod
    def from_payload(cls, payload: dict) -> "AgentJobAssignment":
        return cls(
            job_id=str(payload["id"]),
            conversation_id=(
                str(payload["conversation_id"]) if payload.get("conversation_id") else None
            ),
            profile=str(payload.get("profile") or "ads"),
            job_type=str(payload["job_type"]),
            status=str(payload["status"]),
            hermes_session_id=(
                str(payload["hermes_session_id"])
                if payload.get("hermes_session_id")
                else None
            ),
            payload=dict(payload.get("payload_json") or {}),
        )
