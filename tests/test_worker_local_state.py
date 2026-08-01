from __future__ import annotations

import httpx

from workers.agent.config import WorkerConfig
from workers.agent.control_plane import ControlPlaneClient


def config(tmp_path) -> WorkerConfig:
    return WorkerConfig(
        control_plane_url="https://control.example.test",
        shared_secret="legacy",
        worker_key="worker-01",
        worker_name="Worker 01",
        poll_seconds=1,
        heartbeat_seconds=10,
        data_dir=tmp_path,
        browser_enabled=False,
        display_base=190,
        vnc_port_base=15900,
        web_port_base=16080,
        debug_port_base=19220,
        slot_count=1,
    )


def test_terminal_sync_is_buffered_and_replayed_in_order(tmp_path):
    client = ControlPlaneClient(config(tmp_path))
    client.worker_id = "worker-id"
    client.state.set_value("worker_id", "worker-id")
    client.state.save_assignment(
        "execution",
        "job-1",
        {"id": "job-1", "campaign_draft_id": "c", "facebook_account_id": "f", "profile_key": "p", "meta_ad_account_id": "act_1", "status": "claimed", "payload_json": {}},
    )
    client.http.close()
    client.http = httpx.Client(
        base_url="https://control.example.test",
        transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request))),
    )
    client.sync_execution_job("job-1", status="succeeded", result_json={"ok": True})
    assert client.state.outbox_count() == 1
    assert client.state.resumable_assignment("execution") is None

    client.http.close()
    client.http = httpx.Client(
        base_url="https://control.example.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "succeeded"})),
    )
    assert client.flush_outbox() == 1
    assert client.state.outbox_count() == 0
    client.close()
