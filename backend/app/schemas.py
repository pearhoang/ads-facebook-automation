from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkerRegisterRequest(BaseModel):
    worker_key: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)


class WorkerView(ORMModel):
    id: str
    worker_key: str
    display_name: str
    status: str
    last_seen_at: datetime
    lifecycle_status: str = "active"
    runtime_version: str | None = None
    agent_version: str | None = None
    capabilities_json: dict = Field(default_factory=dict)
    last_error: str | None = None
    host: str | None = None
    ssh_user: str | None = None
    ssh_host_fingerprint: str | None = None
    ssh_password_configured: bool = False
    install_status: str = "registered"
    installed_at: datetime | None = None
    drained_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkerHeartbeatRequest(BaseModel):
    runtime_version: str | None = Field(default=None, max_length=80)
    agent_version: str | None = Field(default=None, max_length=80)
    capabilities: dict | None = None
    last_error: str | None = Field(default=None, max_length=2000)


class BotNodeEnrollmentCreateRequest(BaseModel):
    worker_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(min_length=2, max_length=160)
    repo_url: str | None = Field(default=None, max_length=2048)
    repo_branch: str | None = Field(default=None, max_length=120)


class BotNodeRemoteInstallRequest(BaseModel):
    host: str = Field(min_length=3, max_length=255, pattern=r"^[a-zA-Z0-9.:-]+$")
    ssh_user: str = Field(default="root", min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    ssh_password: SecretStr = Field(min_length=1, max_length=1024)
    worker_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(min_length=2, max_length=160)
    repo_url: str | None = Field(default=None, max_length=2048)
    repo_branch: str | None = Field(default=None, max_length=120)
    provider_name: str = Field(default="custom", min_length=1, max_length=80)
    provider_base_url: str = Field(min_length=8, max_length=2048)
    provider_model: str = Field(min_length=1, max_length=160)
    provider_thinking_mode: str = Field(default="auto", pattern=r"^(auto|enabled|disabled)$")
    provider_reasoning_effort: str = Field(
        default="provider_default",
        pattern=r"^(provider_default|minimal|low|medium|high|xhigh|max|ultra)$",
    )
    provider_api_key: SecretStr | None = Field(default=None, max_length=4096)
    telegram_bot_token: SecretStr = Field(min_length=20, max_length=256)
    telegram_allowed_users: str = Field(min_length=1, max_length=512)

    @field_validator("provider_base_url")
    @classmethod
    def validate_provider_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("Base URL phải dùng HTTPS, trừ endpoint localhost.")
        return normalized

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_bot_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("Telegram Bot Token không đúng định dạng BotFather.")
        return SecretStr(token)

    @field_validator("telegram_allowed_users")
    @classmethod
    def validate_telegram_allowed_users(cls, value: str) -> str:
        user_ids = [item.strip() for item in value.split(",") if item.strip()]
        if not user_ids or any(not re.fullmatch(r"[1-9][0-9]{3,19}", item) for item in user_ids):
            raise ValueError("Telegram user ID phải là số, nhiều ID cách nhau bằng dấu phẩy.")
        return ",".join(dict.fromkeys(user_ids))


class BotNodeEditRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    host: str = Field(min_length=3, max_length=255, pattern=r"^[a-zA-Z0-9.:-]+$")
    ssh_user: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9._-]+$")
    ssh_password: SecretStr | None = Field(default=None, min_length=1, max_length=1024)


class HermesDashboardPasswordRotateRequest(BaseModel):
    new_password: SecretStr = Field(min_length=4, max_length=1024)
    new_password_confirmation: SecretStr = Field(min_length=4, max_length=1024)

    @model_validator(mode="after")
    def confirm_new_password(self):
        if self.new_password.get_secret_value() != self.new_password_confirmation.get_secret_value():
            raise ValueError("Xác nhận mật khẩu Dashboard mới không khớp.")
        return self


class WorkerOperationView(ORMModel):
    id: str
    tenant_id: str
    worker_id: str | None
    operation_type: str
    status: str
    host: str
    ssh_user: str
    message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class BotNodeEnrollmentView(BaseModel):
    id: str
    worker_key: str
    display_name: str
    expires_at: datetime
    enrollment_token: str
    install_command: str


class BotNodeEnrollRequest(BaseModel):
    enrollment_token: str = Field(min_length=32, max_length=256)
    runtime_version: str | None = Field(default=None, max_length=80)
    agent_version: str | None = Field(default=None, max_length=80)
    capabilities: dict = Field(default_factory=dict)


class BotNodeEnrollResponse(BaseModel):
    worker: WorkerView
    worker_credential: str


class AIProviderConfigUpdateRequest(BaseModel):
    provider_type: str = Field(default="openai_compatible", max_length=40)
    provider_name: str = Field(default="custom", min_length=1, max_length=80)
    base_url: str = Field(min_length=8, max_length=2048)
    model: str = Field(min_length=1, max_length=160)
    thinking_mode: str = Field(default="auto", pattern=r"^(auto|enabled|disabled)$")
    reasoning_effort: str = Field(
        default="provider_default",
        pattern=r"^(provider_default|minimal|low|medium|high|xhigh|max|ultra)$",
    )
    agent_permission_mode: str = Field(
        default="ads_safe",
        pattern=r"^(ads_safe|experimental_full)$",
    )
    api_key: str | None = Field(default=None, max_length=4096)
    execution_scope: str = Field(default="worker", pattern=r"^worker$")
    worker_id: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("Base URL phải dùng HTTPS, trừ endpoint localhost.")
        return normalized

    @model_validator(mode="after")
    def validate_scope(self):
        if self.execution_scope == "worker" and not self.worker_id:
            raise ValueError("Hãy chọn Bot VPS chạy Hermes.")
        return self


class AIProviderConfigView(BaseModel):
    configured: bool
    provider_type: str | None = None
    provider_name: str | None = None
    base_url: str | None = None
    model: str | None = None
    thinking_mode: str | None = None
    reasoning_effort: str | None = None
    agent_permission_mode: str | None = None
    api_key_masked: str | None = None
    execution_scope: str | None = None
    worker_id: str | None = None
    status: str | None = None
    last_test_status: str | None = None
    last_test_error: str | None = None
    last_tested_at: datetime | None = None
    updated_at: datetime | None = None


class WorkerAIProviderRuntimeView(BaseModel):
    provider_type: str
    provider_name: str
    base_url: str
    model: str
    thinking_mode: str
    reasoning_effort: str
    agent_permission_mode: str
    api_key: str | None


class AgentConversationCreateRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=36)
    profile: str = Field(default="ads", pattern=r"^ads$")
    title: str = Field(default="Cuộc trò chuyện mới", min_length=1, max_length=240)


class AgentConversationView(ORMModel):
    id: str
    tenant_id: str
    worker_id: str
    profile: str
    hermes_session_id: str | None
    source: str
    title: str
    status: str
    metadata_json: dict
    last_synced_at: datetime | None
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class AgentTextAttachmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    media_type: str = Field(default="text/plain", min_length=1, max_length=100)
    content_base64: str = Field(min_length=1, max_length=180000)


class AgentMessageCreateRequest(BaseModel):
    content: str = Field(default="", max_length=24000)
    attachments: list[AgentTextAttachmentRequest] = Field(default_factory=list, max_length=3)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_visible_payload(self):
        if not self.content and not self.attachments:
            raise ValueError("Tin nhắn hoặc tệp đính kèm không được để trống.")
        return self


class AgentMessageView(ORMModel):
    id: str
    tenant_id: str
    conversation_id: str
    role: str
    content: str
    source: str
    metadata_json: dict
    created_at: datetime


class AgentSyncRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=36)
    profile: str = Field(default="ads", pattern=r"^ads$")


class AgentJobView(ORMModel):
    id: str
    tenant_id: str
    worker_id: str
    conversation_id: str | None
    profile: str
    job_type: str
    status: str
    result_json: dict
    last_error: str | None
    attempt_count: int
    requested_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime

    @field_validator("last_error", mode="before")
    @classmethod
    def hide_internal_hermes_error(cls, value):
        if not value:
            return value
        text = str(value)
        if "127.0.0.1" in text or "Server error '500" in text:
            return "Hermes chưa thể xử lý yêu cầu. Hãy kiểm tra cấu hình provider trong Hermes Agents rồi thử lại."
        return text


class WorkerAgentJobItem(AgentJobView):
    hermes_session_id: str | None = None
    payload_json: dict


class AgentJobSyncRequest(BaseModel):
    status: str = Field(pattern=r"^(running|succeeded|failed)$")
    result_json: dict = Field(default_factory=dict)
    last_error: str | None = Field(default=None, max_length=8000)


class AgentKPIQuery(BaseModel):
    ad_account_id: str | None = Field(default=None, max_length=36)


class AgentCampaignQuery(BaseModel):
    ad_account_id: str | None = Field(default=None, max_length=36)
    status: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=20, ge=1, le=100)


class AgentReportRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    lookback_days: int = Field(default=7, ge=1, le=90)


class AccountCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    assigned_worker_id: str


class AccountView(ORMModel):
    id: str
    tenant_id: str
    assigned_worker_id: str
    label: str
    profile_key: str
    status: str
    facebook_user_id: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class BrowserSessionView(ORMModel):
    id: str
    tenant_id: str
    account_id: str
    worker_id: str
    status: str
    launch_url: str | None
    novnc_url: str | None
    web_port: int | None
    last_error: str | None
    requested_at: datetime
    updated_at: datetime
    expires_at: datetime
    closed_at: datetime | None


class WorkerBrowserSessionItem(BrowserSessionView):
    profile_key: str


class BrowserSessionSyncRequest(BaseModel):
    status: str
    novnc_url: str | None = None
    web_port: int | None = Field(default=None, ge=1, le=65535)
    last_error: str | None = None
    facebook_user_id: str | None = None


class BrowserSessionCreateRequest(BaseModel):
    launch_url: str | None = Field(default=None, max_length=4096)


class HealthView(BaseModel):
    status: str


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    tenant_id: str | None = Field(default=None, max_length=36)


class AuthPasswordChangeRequest(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=4, max_length=1024)
    new_password_confirmation: SecretStr = Field(min_length=4, max_length=1024)

    @model_validator(mode="after")
    def confirm_new_password(self):
        if self.new_password.get_secret_value() != self.new_password_confirmation.get_secret_value():
            raise ValueError("Xác nhận mật khẩu mới không khớp.")
        return self


class AuthView(BaseModel):
    user_id: str
    email: str
    display_name: str
    tenant_id: str
    tenant_name: str
    role: str


class AdAccountCreateRequest(BaseModel):
    facebook_account_id: str = Field(min_length=1, max_length=36)
    meta_ad_account_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    currency: str = Field(min_length=3, max_length=3)
    timezone_name: str = Field(min_length=1, max_length=80)

    @field_validator("meta_ad_account_id", "label", "timezone_name")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class AdAccountUpdateRequest(BaseModel):
    facebook_account_id: str | None = Field(default=None, min_length=1, max_length=36)
    meta_ad_account_id: str | None = Field(default=None, min_length=1, max_length=80)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone_name: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("meta_ad_account_id", "label", "timezone_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường để cập nhật ad account.")
        return self


class AdAccountView(ORMModel):
    id: str
    tenant_id: str
    facebook_account_id: str
    meta_ad_account_id: str
    label: str
    currency: str
    timezone_name: str
    status: str
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class MetaResourceCreateRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    kind: str = Field(
        pattern="^(page|instagram_account|dataset|instant_form|app)$"
    )
    label: str = Field(min_length=1, max_length=200)
    external_id: str | None = Field(default=None, max_length=160)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("label", "external_id")
    @classmethod
    def normalize_resource_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None


class MetaResourceVerifyRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=80)


class MetaResourceView(ORMModel):
    id: str
    tenant_id: str
    ad_account_id: str
    kind: str
    label: str
    external_id: str | None
    status: str
    metadata_json: dict
    created_by_user_id: str
    verified_by_user_id: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreativeAssetView(ORMModel):
    id: str
    tenant_id: str
    ad_account_id: str
    label: str
    file_name: str
    content_type: str
    byte_size: int
    sha256: str
    status: str
    metadata_json: dict
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class CampaignDraftCreateRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=40)
    daily_budget_minor: int = Field(gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict = Field(default_factory=dict)
    creative_json: dict = Field(default_factory=dict)

    @field_validator("name", "objective")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("Thời gian kết thúc phải sau thời gian bắt đầu.")
        return self


class CampaignDraftUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    objective: str | None = Field(default=None, min_length=1, max_length=40)
    daily_budget_minor: int | None = Field(default=None, gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict | None = None
    creative_json: dict | None = None

    @field_validator("name", "objective")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class CampaignDraftView(ORMModel):
    id: str
    tenant_id: str
    ad_account_id: str
    name: str
    objective: str
    daily_budget_minor: int
    currency: str
    start_at: datetime | None
    end_at: datetime | None
    targeting_json: dict
    creative_json: dict
    status: str
    version: int
    created_by_user_id: str
    updated_by_user_id: str
    submitted_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ObjectiveSpecView(BaseModel):
    key: str
    label: str
    setup_mode: str
    default_conversion_location: str
    conversion_location_label: str
    performance_goal: str
    performance_goal_label: str
    required_fields: list[str]
    optional_fields: list[str]
    manual_setup_label: str | None
    field_actions: list[dict]
    field_labels: dict[str, str]
    automation_level: str
    surveyed_at: str


class ApprovalDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ApprovalRequestView(ORMModel):
    id: str
    tenant_id: str
    campaign_draft_id: str
    status: str
    requested_by_user_id: str
    decided_by_user_id: str | None
    snapshot_json: dict
    decision_note: str | None
    requested_at: datetime
    decided_at: datetime | None


class AuditEventView(ORMModel):
    id: str
    tenant_id: str
    actor_user_id: str | None
    actor_type: str
    action: str
    entity_type: str
    entity_id: str
    payload_json: dict
    created_at: datetime


class ExecutionPreviewView(BaseModel):
    campaign_id: str
    campaign_name: str
    campaign_version: int
    ad_account_label: str
    meta_ad_account_id: str
    facebook_account_label: str
    facebook_account_status: str
    worker_name: str
    worker_status: str
    active_browser_session: bool
    can_run_preflight: bool
    can_build_draft: bool
    blockers: list[str]
    draft_blockers: list[str]
    draft_warnings: list[str]
    approved_snapshot: dict


class ExecutionJobCreateRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=36)
    job_type: str = Field(default="preflight", pattern="^(preflight|draft_build)$")
    confirmation: str = Field(min_length=1, max_length=80)


class ExecutionJobRetryRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=80)


class ExecutionJobView(ORMModel):
    id: str
    tenant_id: str
    campaign_draft_id: str
    approval_request_id: str
    ad_account_id: str
    facebook_account_id: str
    worker_id: str
    job_type: str
    status: str
    payload_json: dict
    result_json: dict
    last_error: str | None
    requested_by_user_id: str
    attempt_count: int
    lease_expires_at: datetime | None
    requested_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class WorkerExecutionJobItem(ExecutionJobView):
    profile_key: str
    meta_ad_account_id: str


class ExecutionJobSyncRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    result_json: dict = Field(default_factory=dict)
    last_error: str | None = Field(default=None, max_length=4000)


class ExecutionArtifactView(ORMModel):
    id: str
    tenant_id: str
    execution_job_id: str
    kind: str
    content_type: str
    byte_size: int
    sha256: str
    metadata_json: dict
    created_at: datetime


class AdAutomationEventView(ORMModel):
    id: str
    tenant_id: str
    request_id: str
    actor_type: str
    event_type: str
    stage: str
    message: str
    payload_json: dict
    created_at: datetime


class AdAutomationRequestSummaryView(ORMModel):
    id: str
    tenant_id: str
    worker_id: str
    facebook_account_id: str
    ad_account_id: str
    campaign_draft_id: str | None
    approval_request_id: str | None
    execution_job_id: str | None
    source: str
    source_session_id: str | None
    source_message_id: str | None
    intent: str
    request_text: str
    title: str
    status: str
    stage: str
    progress_message: str
    plan_json: dict
    resolution_json: dict
    recovery_json: dict
    last_error: str | None
    requested_by_user_id: str | None
    attempt_count: int
    recovery_count: int
    requested_at: datetime
    completed_at: datetime | None
    updated_at: datetime


class AgentCampaignPrepareRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    request_text: str = Field(min_length=1, max_length=12000)
    title: str = Field(min_length=1, max_length=240)
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=40)
    daily_budget_minor: int = Field(gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    targeting_json: dict = Field(default_factory=dict)
    creative_json: dict = Field(default_factory=dict)
    source: str = Field(default="telegram", pattern="^(telegram|hermes|web|import)$")
    source_session_id: str | None = Field(default=None, max_length=255)
    source_message_id: str | None = Field(default=None, max_length=160)


class AgentCampaignConfirmRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=36)
    decision: str = Field(pattern="^(execute_draft|cancel)$")
    note: str | None = Field(default=None, max_length=2000)


class AgentWorkStatusRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=36)


class AgentWorkflowLearningRequest(BaseModel):
    learning_key: str = Field(min_length=1, max_length=160)
    symptom: str = Field(min_length=1, max_length=4000)
    cause: str | None = Field(default=None, max_length=4000)
    recovery_plan_json: dict = Field(default_factory=dict)


class ReportScheduleCreateRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    local_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    lookback_days: int = Field(default=7, ge=1, le=90)
    telegram_chat_id: str | None = Field(default=None, max_length=80)

    @field_validator("telegram_chat_id")
    @classmethod
    def normalize_chat_id(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ReportScheduleUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(enabled|paused)$")
    local_time: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    lookback_days: int | None = Field(default=None, ge=1, le=90)
    telegram_chat_id: str | None = Field(default=None, max_length=80)

    @field_validator("telegram_chat_id")
    @classmethod
    def normalize_optional_chat_id(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường để cập nhật lịch báo cáo.")
        return self


class ReportScheduleView(ORMModel):
    id: str
    tenant_id: str
    ad_account_id: str
    worker_id: str
    status: str
    cadence: str
    local_time: str
    timezone_name: str
    lookback_days: int
    telegram_chat_id: str | None
    next_run_at: datetime
    last_enqueued_at: datetime | None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class ReportJobCreateRequest(BaseModel):
    ad_account_id: str = Field(min_length=1, max_length=36)
    lookback_days: int = Field(default=7, ge=1, le=90)
    telegram_chat_id: str | None = Field(default=None, max_length=80)
    confirmation: str = Field(min_length=1, max_length=80)

    @field_validator("telegram_chat_id")
    @classmethod
    def normalize_manual_chat_id(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ReportJobView(ORMModel):
    id: str
    tenant_id: str
    ad_account_id: str
    facebook_account_id: str
    worker_id: str
    schedule_id: str | None
    trigger: str
    status: str
    range_start: date
    range_end: date
    payload_json: dict
    result_json: dict
    delivery_status: str
    last_error: str | None
    requested_by_user_id: str | None
    attempt_count: int
    lease_expires_at: datetime | None
    requested_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class WorkerReportJobItem(ReportJobView):
    profile_key: str
    meta_ad_account_id: str
    ad_account_label: str
    currency: str


class ReportJobSyncRequest(BaseModel):
    status: str = Field(pattern="^(running|succeeded|failed)$")
    result_json: dict = Field(default_factory=dict)
    last_error: str | None = Field(default=None, max_length=4000)


class ReportSnapshotView(ORMModel):
    id: str
    tenant_id: str
    report_job_id: str
    ad_account_id: str
    range_start: date
    range_end: date
    source: str
    currency: str
    totals_json: dict
    campaigns_json: list
    metadata_json: dict
    collected_at: datetime
    created_at: datetime
