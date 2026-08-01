from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend.app.services import objective_specs
from cleanup_meta_discovery_draft import CONFIRMATION as CLEANUP_CONFIRMATION
from cleanup_meta_discovery_draft import DiscoveryDraftCleanup
from workers.agent.config import WorkerConfig
from workers.agent.contracts import ExecutionJobAssignment
from workers.agent.execution import MetaDraftBuildRuntime


CONFIRMATION = "SMOKE META FIELD FILLING DRAFT ONLY"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def campaign_id_from_result(result: dict) -> str:
    current_url = str(result.get("current_url") or "")
    values = parse_qs(urlparse(current_url).query).get("selected_campaign_ids") or []
    campaign_id = str(values[0]) if values else ""
    if not campaign_id.isdigit():
        raise RuntimeError("Không lấy được exact Meta campaign ID từ field-filling result.")
    return campaign_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--profile-key", required=True)
    parser.add_argument("--ad-account-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Invalid field-filling smoke confirmation.")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    campaign_name = f"[DISCOVERY {stamp}] Phase 6 Sales fields"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = WorkerConfig.from_env()
    adapter_spec = objective_specs.get_spec("sales")
    if adapter_spec is None:
        raise RuntimeError("Sales adapter is unavailable.")
    assignment = ExecutionJobAssignment(
        job_id=f"phase6-smoke-{stamp}",
        campaign_draft_id=f"phase6-smoke-{stamp}",
        facebook_account_id="phase6-discovery",
        profile_key=args.profile_key,
        meta_ad_account_id=args.ad_account_id,
        status="claimed",
        payload={
            "ad_account": {
                "meta_ad_account_id": args.ad_account_id,
                "currency": "VND",
                "timezone_name": "Asia/Ho_Chi_Minh",
            },
            "draft_spec": {
                "campaign_name": campaign_name,
                "adset_name": f"{campaign_name} — Ad Set",
                "ad_name": f"{campaign_name} — Ad",
                "objective": "sales",
                "daily_budget_minor": 100000,
                "targeting": {
                    "conversion_location": "website",
                    "performance_goal": "conversions",
                    "countries": ["VN"],
                    "page_name": "[DISCOVERY MISSING PAGE]",
                },
                "creative": {
                    "primary_text": "Nội dung kiểm thử Phase 6 — không publish.",
                    "headline": "Kiểm thử field-filling",
                    "destination_url": "https://example.com/phase-6-smoke",
                    "cta": "LEARN_MORE",
                },
            },
            "objective_adapter": adapter_spec.as_payload(),
            "safety": {
                "mode": "draft_only",
                "allow_click": True,
                "allow_publish": False,
                "stop_before": "publish",
            },
        },
    )

    result, artifacts = MetaDraftBuildRuntime(config).run(assignment)
    for kind, content in artifacts.items():
        (output_dir / f"{kind}.png").write_bytes(content)
    campaign_id = campaign_id_from_result(result)
    envelope = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "result": result,
        "cleanup_confirmation": CLEANUP_CONFIRMATION,
    }
    (output_dir / "field-filling-result.json").write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if result.get("safety", {}).get("published") is not False:
        raise RuntimeError("Field-filling smoke violated published=false.")

    cleanup_result = DiscoveryDraftCleanup(config).run(
        profile_key=args.profile_key,
        ad_account_id=args.ad_account_id,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        output_dir=output_dir / "cleanup",
        delete=True,
    )
    envelope["cleanup"] = cleanup_result
    (output_dir / "result.json").write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not cleanup_result.get("deleted"):
        raise RuntimeError("Exact Phase 6 discovery draft was not deleted.")
    print(json.dumps(envelope, ensure_ascii=False))


if __name__ == "__main__":
    main()
