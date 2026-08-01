from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


FIELD_LABELS = {
    "targeting.countries": "quốc gia targeting",
    "targeting.age_min": "tuổi tối thiểu",
    "targeting.age_max": "tuổi tối đa",
    "targeting.placements": "vị trí quảng cáo",
    "targeting.page_name": "Page Facebook",
    "targeting.messaging_destination": "kênh nhận tin nhắn",
    "targeting.app_name": "ứng dụng",
    "targeting.app_store_country": "quốc gia cửa hàng ứng dụng",
    "creative.primary_text": "primary text",
    "creative.destination_url": "destination URL",
    "creative.lead_form_name": "Instant Form",
    "creative.headline": "headline",
    "creative.cta": "CTA",
    "creative.asset_id": "creative asset",
    "creative.asset_local_path": "creative asset",
    "targeting.dataset_name": "Pixel/dataset",
    "targeting.conversion_event": "conversion event",
}


@dataclass(frozen=True, slots=True)
class FieldActionSpec:
    field_path: str
    stage: str
    handler: str
    terminal: bool = True
    required: bool | None = None


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    key: str
    label: str
    setup_mode: str
    default_conversion_location: str
    conversion_location_label: str
    performance_goal: str
    performance_goal_label: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    manual_setup_label: str | None = None
    field_actions: tuple[FieldActionSpec, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_fields"] = list(self.required_fields)
        payload["optional_fields"] = list(self.optional_fields)
        payload["field_actions"] = [asdict(action) for action in self.field_actions]
        payload["field_labels"] = {
            field: FIELD_LABELS[field]
            for field in dict.fromkeys(
                (
                    *self.required_fields,
                    *self.optional_fields,
                    *(action.field_path for action in self.field_actions),
                )
            )
        }
        payload["automation_level"] = "field_filling"
        payload["surveyed_at"] = "2026-07-31"
        return payload


COMMON_ADSET_ACTIONS = (
    FieldActionSpec("targeting.countries", "adset", "countries_exact", required=True),
    FieldActionSpec("targeting.age_min", "adset", "age_min"),
    FieldActionSpec("targeting.age_max", "adset", "age_max"),
    FieldActionSpec("targeting.placements", "adset", "placements"),
)
COMMON_AD_ACTIONS = (
    FieldActionSpec(
        "creative.asset_local_path",
        "ad",
        "media_upload",
        required=True,
    ),
)


OBJECTIVE_SPECS = {
    "awareness": ObjectiveSpec(
        key="awareness",
        label="Mức độ nhận biết",
        setup_mode="direct",
        default_conversion_location="awareness",
        conversion_location_label="Mức độ nhận biết",
        performance_goal="reach",
        performance_goal_label="Tối đa hóa số người tiếp cận quảng cáo",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "creative.primary_text",
        ),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.page_name", "adset", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
        ),
    ),
    "traffic": ObjectiveSpec(
        key="traffic",
        label="Lưu lượng truy cập",
        setup_mode="manual",
        manual_setup_label="Chiến dịch lưu lượng truy cập thủ công",
        default_conversion_location="website",
        conversion_location_label="Trang web",
        performance_goal="landing_page_views",
        performance_goal_label="Tăng tối đa số lượt xem trang đích",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "creative.primary_text",
            "creative.destination_url",
        ),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.page_name", "ad", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec("creative.destination_url", "ad", "destination_url"),
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
        ),
    ),
    "engagement": ObjectiveSpec(
        key="engagement",
        label="Lượt tương tác",
        setup_mode="direct",
        default_conversion_location="messaging_apps",
        conversion_location_label="Đích đến của tin nhắn",
        performance_goal="conversations",
        performance_goal_label="Tối đa hóa số cuộc trò chuyện",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "targeting.messaging_destination",
            "creative.primary_text",
        ),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.page_name", "ad", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec(
                "targeting.messaging_destination",
                "ad",
                "messaging_destination",
            ),
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
        ),
    ),
    "leads": ObjectiveSpec(
        key="leads",
        label="Khách hàng tiềm năng",
        setup_mode="direct",
        default_conversion_location="instant_forms",
        conversion_location_label="Mẫu phản hồi tức thì",
        performance_goal="leads",
        performance_goal_label="Tối đa hóa số khách hàng tiềm năng",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "creative.lead_form_name",
            "creative.primary_text",
        ),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.page_name", "adset", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec("creative.lead_form_name", "ad", "lead_form"),
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
        ),
    ),
    "app_promotion": ObjectiveSpec(
        key="app_promotion",
        label="Quảng cáo ứng dụng",
        setup_mode="direct",
        default_conversion_location="app_store",
        conversion_location_label="Cửa hàng ứng dụng",
        performance_goal="app_installs",
        performance_goal_label="Tối đa hóa số lượt cài đặt ứng dụng",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "targeting.app_name",
            "creative.primary_text",
        ),
        optional_fields=("targeting.app_store_country",),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.app_name", "adset", "app_name"),
            FieldActionSpec(
                "targeting.app_store_country",
                "adset",
                "app_store_country",
            ),
            FieldActionSpec("targeting.page_name", "ad", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
        ),
    ),
    "sales": ObjectiveSpec(
        key="sales",
        label="Doanh số",
        setup_mode="direct",
        default_conversion_location="website",
        conversion_location_label="Trang web",
        performance_goal="conversions",
        performance_goal_label="Tối đa hóa số lượt chuyển đổi",
        required_fields=(
            "targeting.page_name",
            "targeting.countries",
            "creative.asset_id",
            "creative.primary_text",
            "creative.destination_url",
        ),
        optional_fields=("targeting.dataset_name", "targeting.conversion_event"),
        field_actions=(
            *COMMON_ADSET_ACTIONS,
            FieldActionSpec("targeting.page_name", "ad", "page_exact"),
            *COMMON_AD_ACTIONS,
            FieldActionSpec("creative.destination_url", "ad", "destination_url"),
            FieldActionSpec("creative.primary_text", "ad", "primary_text"),
            FieldActionSpec("creative.headline", "ad", "headline"),
            FieldActionSpec("creative.cta", "ad", "cta"),
            FieldActionSpec("targeting.dataset_name", "ad", "dataset"),
            FieldActionSpec("targeting.conversion_event", "ad", "conversion_event"),
        ),
    ),
}


def list_specs() -> list[dict[str, Any]]:
    return [spec.as_payload() for spec in OBJECTIVE_SPECS.values()]


def get_spec(objective: str) -> ObjectiveSpec | None:
    return OBJECTIVE_SPECS.get(str(objective or "").strip())


def read_path(targeting: dict, creative: dict, path: str) -> Any:
    root, key = path.split(".", 1)
    source = targeting if root == "targeting" else creative
    return source.get(key)


def build_spec_warnings(
    objective: str,
    targeting: dict,
    creative: dict,
) -> tuple[list[str], list[str]]:
    spec = get_spec(objective)
    if spec is None:
        return [f"Objective '{objective}' chưa có adapter đã khảo sát."], []
    blockers: list[str] = []
    configured_location = str(targeting.get("conversion_location") or "").strip()
    if configured_location and configured_location != spec.default_conversion_location:
        blockers.append(
            "Worker chỉ tự động hóa default path đã khảo sát "
            f"'{spec.conversion_location_label}' cho objective {spec.label}."
        )
    warnings = [
        f"Thiếu {FIELD_LABELS[field]}; worker sẽ dừng trước Review để người dùng hoàn thiện."
        for field in spec.required_fields
        if not str(read_path(targeting, creative, field) or "").strip()
    ]
    warnings.extend(
        f"Chưa cấu hình {FIELD_LABELS[field]}; Meta có thể giữ mặc định hoặc yêu cầu bổ sung."
        for field in spec.optional_fields
        if not str(read_path(targeting, creative, field) or "").strip()
    )
    if not targeting.get("countries"):
        warnings.append(
            "Chưa có quốc gia targeting có cấu trúc; Meta có thể giữ mặc định tài khoản."
        )
    return blockers, warnings
