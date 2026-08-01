from __future__ import annotations

from pathlib import Path

from workers.agent.config import WorkerConfig
from workers.agent.contracts import BrowserSessionAssignment
from workers.agent.sessions import BrowserSessionSupervisor


class FakeRuntime:
    def __init__(self):
        self.records = {}
        self.stopped = []

    def load_persisted_sessions(self):
        return dict(self.records)

    def launch(self, record):
        return {
            "novnc_url": f"https://example.test/browser/{record['session_id']}/vnc.html",
            "web_port": record["web_port"],
            "chromium_pid": 100,
            "x11vnc_pid": 101,
            "websockify_pid": 102,
            "session_path": f"/tmp/{record['session_id']}",
        }

    def save_session_record(self, record):
        self.records[record["session_id"]] = dict(record)

    def is_running(self, record):
        return record["session_id"] not in self.stopped

    def stop(self, record):
        self.stopped.append(record["session_id"])
        self.records.pop(record["session_id"], None)


class FakeClient:
    def __init__(self, assignments):
        self.assignments = assignments
        self.syncs = []

    def poll_sessions(self):
        return list(self.assignments)

    def sync_session(self, session_id, **payload):
        self.syncs.append((session_id, payload))


def test_supervisor_launches_and_closes_browser_session(tmp_path: Path):
    config = WorkerConfig(
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
    assignment = BrowserSessionAssignment(
        session_id="session-1",
        account_id="account-1",
        profile_key="profile-1",
        status="requested",
        expires_at="2030-01-01T00:00:00Z",
    )
    client = FakeClient([assignment])
    runtime = FakeRuntime()
    supervisor = BrowserSessionSupervisor(config, client, runtime=runtime)

    supervisor.reconcile()

    assert [payload["status"] for _, payload in client.syncs] == ["starting", "awaiting_user"]
    assert client.syncs[-1][1]["web_port"] == 16080
    assert "session-1" in supervisor.local_sessions

    client.assignments = [
        BrowserSessionAssignment(
            session_id="session-1",
            account_id="account-1",
            profile_key="profile-1",
            status="closing",
            expires_at="2030-01-01T00:00:00Z",
        )
    ]
    supervisor.reconcile()

    assert runtime.stopped == ["session-1"]
    assert client.syncs[-1][1]["status"] == "closed"
