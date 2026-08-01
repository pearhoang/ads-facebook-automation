from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path

from workers.agent.config import WorkerConfig
from workers.agent.contracts import ExecutionJobAssignment
from workers.agent.execution import ExecutionJobSupervisor


@dataclass
class FakeClient:
    assignment: ExecutionJobAssignment | None
    syncs: list[tuple[str, str, dict, str | None]] = field(default_factory=list)
    screenshots: list[tuple[str, bytes]] = field(default_factory=list)
    artifacts: list[tuple[str, str, bytes]] = field(default_factory=list)
    asset_downloads: list[tuple[str, str, Path]] = field(default_factory=list)

    def poll_execution_job(self):
        assignment, self.assignment = self.assignment, None
        return assignment

    def sync_execution_job(self, job_id, *, status, result_json=None, last_error=None):
        self.syncs.append((job_id, status, result_json or {}, last_error))

    def upload_execution_screenshot(self, job_id, content):
        self.screenshots.append((job_id, content))

    def upload_execution_artifact(self, job_id, kind, content):
        self.artifacts.append((job_id, kind, content))

    def download_execution_asset(self, job_id, asset_id, target, expected_sha256):
        content = b"phase-7-asset"
        assert hashlib.sha256(content).hexdigest() == expected_sha256
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self.asset_downloads.append((job_id, asset_id, target))
        return target


class FakeRuntime:
    def run(self, assignment):
        return (
            {
                "readiness": "ready",
                "ready": True,
                "safety": {"clicked": False, "published": False},
            },
            b"png",
        )


class FakeDraftRuntime:
    def run(self, assignment):
        return (
            {
                "readiness": "awaiting_user",
                "ready": False,
                "phase": "adset",
                "safety": {"clicked": True, "published": False},
            },
            {"campaign_step": b"campaign", "adset_step": b"adset"},
        )


def config(tmp_path: Path) -> WorkerConfig:
    return WorkerConfig(
        control_plane_url="http://control-plane.test",
        shared_secret="secret",
        worker_key="worker-1",
        worker_name="Worker 1",
        poll_seconds=1,
        heartbeat_seconds=10,
        data_dir=tmp_path,
        browser_enabled=True,
        display_base=190,
        vnc_port_base=15900,
        web_port_base=16080,
        debug_port_base=19220,
        slot_count=2,
    )


def assignment() -> ExecutionJobAssignment:
    return ExecutionJobAssignment(
        job_id="job-1",
        campaign_draft_id="campaign-1",
        facebook_account_id="facebook-1",
        profile_key="profile-1",
        meta_ad_account_id="act_123",
        status="claimed",
        payload={"safety": {"allow_click": False, "allow_publish": False}},
    )


def test_execution_supervisor_uploads_artifact_and_succeeds(tmp_path: Path):
    client = FakeClient(assignment())
    supervisor = ExecutionJobSupervisor(config(tmp_path), client, runtime=FakeRuntime())
    supervisor.reconcile(set())
    assert [item[1] for item in client.syncs] == ["running", "succeeded"]
    assert client.screenshots == [("job-1", b"png")]
    assert client.syncs[-1][2]["safety"]["published"] is False


def test_execution_supervisor_refuses_busy_profile(tmp_path: Path):
    client = FakeClient(assignment())
    supervisor = ExecutionJobSupervisor(config(tmp_path), client, runtime=FakeRuntime())
    supervisor.reconcile({"profile-1"})
    assert [item[1] for item in client.syncs] == ["awaiting_user"]
    assert client.screenshots == []


def test_execution_supervisor_routes_draft_builder_and_uploads_checkpoints(tmp_path: Path):
    item = assignment()
    item = ExecutionJobAssignment(
        job_id=item.job_id,
        campaign_draft_id=item.campaign_draft_id,
        facebook_account_id=item.facebook_account_id,
        profile_key=item.profile_key,
        meta_ad_account_id=item.meta_ad_account_id,
        status=item.status,
        payload={"safety": {"mode": "draft_only", "allow_click": True, "allow_publish": False}},
    )
    client = FakeClient(item)
    supervisor = ExecutionJobSupervisor(
        config(tmp_path),
        client,
        runtime=FakeRuntime(),
        draft_runtime=FakeDraftRuntime(),
    )
    supervisor.reconcile(set())
    assert [item[1] for item in client.syncs] == ["running", "awaiting_user"]
    assert client.artifacts == [
        ("job-1", "campaign_step", b"campaign"),
        ("job-1", "adset_step", b"adset"),
    ]
    assert client.syncs[-1][2]["safety"]["published"] is False


def test_execution_supervisor_downloads_verified_asset_before_draft_runtime(tmp_path: Path):
    content = b"phase-7-asset"
    item = assignment()
    item = ExecutionJobAssignment(
        job_id=item.job_id,
        campaign_draft_id=item.campaign_draft_id,
        facebook_account_id=item.facebook_account_id,
        profile_key=item.profile_key,
        meta_ad_account_id=item.meta_ad_account_id,
        status=item.status,
        payload={
            "safety": {"mode": "draft_only", "allow_click": True, "allow_publish": False},
            "draft_spec": {
                "creative": {
                    "asset_id": "asset-1",
                    "asset_snapshot": {
                        "id": "asset-1",
                        "file_name": "creative.png",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    },
                }
            },
        },
    )
    client = FakeClient(item)
    supervisor = ExecutionJobSupervisor(
        config(tmp_path),
        client,
        runtime=FakeRuntime(),
        draft_runtime=FakeDraftRuntime(),
    )
    supervisor.reconcile(set())
    assert len(client.asset_downloads) == 1
    target = client.asset_downloads[0][2]
    assert target.read_bytes() == content
    assert item.payload["draft_spec"]["creative"]["asset_local_path"] == str(target)
