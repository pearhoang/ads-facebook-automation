from __future__ import annotations

from dataclasses import dataclass, field

from workers.agent.contracts import ReportJobAssignment
from workers.agent.reporting import ReportJobSupervisor, parse_grid


def assignment() -> ReportJobAssignment:
    return ReportJobAssignment(
        job_id="job-report-1",
        facebook_account_id="facebook-1",
        profile_key="profile-1",
        meta_ad_account_id="act_123",
        ad_account_label="Bán hàng Việt Nam",
        currency="VND",
        status="claimed",
        range_start="2026-07-24",
        range_end="2026-07-30",
        payload={
            "safety": {
                "mode": "report_read_only",
                "allow_filter_click": False,
                "allow_ad_mutation": False,
                "allow_publish": False,
            },
            "delivery": {"channel": "web_only", "telegram_chat_id": None},
        },
    )


@dataclass
class FakeClient:
    item: ReportJobAssignment | None
    syncs: list[dict] = field(default_factory=list)

    def poll_report_job(self):
        item, self.item = self.item, None
        return item

    def sync_report_job(self, job_id, **payload):
        self.syncs.append({"job_id": job_id, **payload})


class FakeRuntime:
    def run(self, _assignment):
        return ({
            "ready": True,
            "data_state": "empty",
            "metrics": {"headers": [], "campaigns": [], "totals": {"campaigns": 0}},
            "safety": {"clicked": False, "ad_mutated": False, "published": False},
        }, b"png")


class FakeDelivery:
    def send(self, _assignment, _result):
        return {"status": "not_requested"}


def test_grid_parser_maps_vietnamese_metrics():
    parsed = parse_grid(
        {
            "headers": ["Chiến dịch", "Kết quả", "Số tiền đã chi tiêu"],
            "rows": [["Campaign A", "12", "240.000 ₫"], ["Campaign B", "3", "60.000 ₫"]],
        },
        "VND",
    )
    assert parsed["totals"]["results"] == 15
    assert parsed["totals"]["amount_spent"] == 300000
    assert parsed["totals"]["cost_per_result"] == 20000
    assert parsed["campaigns"][0]["campaign_name"] == "Campaign A"


def test_report_supervisor_syncs_read_only_result():
    client = FakeClient(assignment())
    supervisor = ReportJobSupervisor(
        config=None,  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
        runtime=FakeRuntime(),  # type: ignore[arg-type]
        delivery=FakeDelivery(),  # type: ignore[arg-type]
    )
    supervisor.reconcile(set())
    assert [item["status"] for item in client.syncs] == ["running", "succeeded"]
    final = client.syncs[-1]["result_json"]
    assert final["safety"] == {"clicked": False, "ad_mutated": False, "published": False}
    assert final["delivery"]["status"] == "not_requested"

