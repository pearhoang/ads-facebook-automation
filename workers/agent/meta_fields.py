from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FieldAction:
    field_path: str
    stage: str
    handler: str
    value: str
    required: bool
    terminal: bool

    def as_result(self, status: str, detail: str) -> dict[str, Any]:
        result = asdict(self)
        result.pop("value", None)
        result.update({"status": status, "detail": detail})
        return result


def read_spec_value(spec: dict, field_path: str) -> str:
    root, separator, key = str(field_path).partition(".")
    if not separator or root not in {"targeting", "creative"}:
        return ""
    source = spec.get(root) or {}
    value = source.get(key)
    if isinstance(value, (list, tuple)):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def build_stage_plan(adapter: dict, spec: dict, stage: str) -> list[FieldAction]:
    required_fields = {str(item) for item in adapter.get("required_fields") or []}
    actions: list[FieldAction] = []
    for item in adapter.get("field_actions") or []:
        if str(item.get("stage") or "") != stage:
            continue
        field_path = str(item.get("field_path") or "").strip()
        handler = str(item.get("handler") or "").strip()
        if not field_path or not handler:
            continue
        actions.append(
            FieldAction(
                field_path=field_path,
                stage=stage,
                handler=handler,
                value=read_spec_value(spec, field_path),
                required=(
                    bool(item.get("required"))
                    if item.get("required") is not None
                    else field_path in required_fields
                ),
                terminal=bool(item.get("terminal", True)),
            )
        )
    if stage == "adset":
        # Page selection can unlock/lazy-render the audience controls. Keep it first
        # even when an older approved adapter snapshot listed common targeting first.
        actions.sort(key=lambda action: 0 if action.handler == "page_exact" else 1)
    return actions


def action_blocks(result: dict) -> bool:
    return bool(
        result.get("required")
        and result.get("terminal")
        and result.get("status") in {"blocked", "not_available", "failed"}
    )
