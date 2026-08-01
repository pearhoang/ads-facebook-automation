from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from websockets.sync.client import connect

from .browser_runtime import (
    BrowserRuntimeManager,
    _build_browser_env,
    _graceful_shutdown_chromium,
)
from .config import WorkerConfig
from .contracts import ReportJobAssignment
from .control_plane import ControlPlaneClient
from .execution import CampaignPreflightRuntime


HEADER_KEYS = {
    "chiến dịch": "campaign_name",
    "campaign": "campaign_name",
    "phân phối": "delivery",
    "delivery": "delivery",
    "kết quả": "results",
    "results": "results",
    "chi phí trên mỗi kết quả": "cost_per_result",
    "cost per result": "cost_per_result",
    "ngân sách": "budget",
    "budget": "budget",
    "số tiền đã chi tiêu": "amount_spent",
    "amount spent": "amount_spent",
    "lượt tiếp cận": "reach",
    "số người tiếp cận": "reach",
    "reach": "reach",
    "lượt hiển thị": "impressions",
    "impressions": "impressions",
    "lượt click vào liên kết": "link_clicks",
    "link clicks": "link_clicks",
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _header_key(value: str) -> str | None:
    normalized = _normalize(value).lower().replace(" ↕", "").replace(" ↑", "").replace(" ↓", "")
    for label, key in HEADER_KEYS.items():
        if normalized == label or normalized.startswith(f"{label} "):
            return key
    return None


def _number(value: str) -> float | None:
    text = _normalize(value)
    if not text or text in {"—", "-", "N/A"}:
        return None
    match = re.search(r"-?[\d][\d.,\s]*", text)
    if not match:
        return None
    numeric = match.group(0).replace(" ", "")
    if "," in numeric and "." in numeric:
        decimal = "," if numeric.rfind(",") > numeric.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        numeric = numeric.replace(thousands, "").replace(decimal, ".")
    elif "," in numeric:
        parts = numeric.split(",")
        numeric = "".join(parts) if len(parts[-1]) == 3 else ".".join(parts)
    elif "." in numeric:
        parts = numeric.split(".")
        numeric = "".join(parts) if len(parts[-1]) == 3 else ".".join(parts)
    try:
        return float(numeric)
    except ValueError:
        return None


def parse_grid(surface: dict, currency: str) -> dict:
    headers = [_normalize(item) for item in surface.get("headers") or []]
    mapped_headers = [_header_key(item) for item in headers]
    campaigns: list[dict] = []
    for raw_cells in surface.get("rows") or []:
        cells = [_normalize(str(item)) for item in raw_cells]
        if not cells or cells == headers:
            continue
        row: dict[str, object] = {}
        raw: dict[str, str] = {}
        for index, cell in enumerate(cells):
            key = mapped_headers[index] if index < len(mapped_headers) else None
            if not key or not cell:
                continue
            raw[key] = cell
            row[key] = cell if key in {"campaign_name", "delivery", "budget"} else _number(cell)
        name = _normalize(str(row.get("campaign_name") or ""))
        if not name or name.lower() in {"chiến dịch", "campaign"}:
            continue
        row["campaign_name"] = name
        row["raw"] = raw
        campaigns.append(row)

    numeric_keys = ("results", "amount_spent", "reach", "impressions", "link_clicks")
    totals = {
        key: sum(float(row[key]) for row in campaigns if isinstance(row.get(key), (int, float)))
        for key in numeric_keys
    }
    totals["campaigns"] = len(campaigns)
    totals["currency"] = currency
    totals["cost_per_result"] = (
        totals["amount_spent"] / totals["results"] if totals["results"] > 0 else None
    )
    return {"headers": headers, "campaigns": campaigns, "totals": totals}


class MetaReportRuntime(CampaignPreflightRuntime):
    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        self.browser_manager = BrowserRuntimeManager(config.data_dir)

    def run(self, assignment: ReportJobAssignment) -> tuple[dict, bytes]:
        safety = assignment.payload.get("safety") or {}
        if safety != {
            "mode": "report_read_only",
            "allow_filter_click": False,
            "allow_ad_mutation": False,
            "allow_publish": False,
        }:
            raise RuntimeError("Report job is missing the strict read-only safety contract.")
        browser_config = self.browser_manager.load_config()
        profile_dir = browser_config.profile_root / assignment.profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile does not exist on worker.")
        job_dir = self.config.data_dir / "report-jobs" / assignment.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        meta_id = assignment.meta_ad_account_id.removeprefix("act_")
        start_url = "https://adsmanager.facebook.com/adsmanager/manage/campaigns?" + urlencode(
            {
                "act": meta_id,
                "date": f"{assignment.range_start}_{assignment.range_end}",
            }
        )
        env = _build_browser_env(
            base_env=os.environ.copy(),
            display=":0",
            profile_dir=profile_dir,
            session_dir=job_dir,
            chromium_bin=browser_config.chromium_bin,
        )
        log_file = (job_dir / "chromium.log").open("ab")
        process = subprocess.Popen(
            [
                browser_config.chromium_bin,
                f"--user-data-dir={profile_dir}",
                "--profile-directory=Default",
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--password-store=basic",
                "--window-size=1600,1000",
                f"--remote-debugging-port={self.config.execution_debug_port}",
                start_url,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            target = self._wait_for_page()
            with connect(
                str(target["webSocketDebuggerUrl"]),
                open_timeout=5,
                max_size=16 * 1024 * 1024,
            ) as socket:
                self._cdp_command(socket, 1, "Page.enable")
                deadline = time.time() + self.config.execution_timeout_seconds
                command_id = 2
                current_url = ""
                body_text = ""
                title = ""
                while time.time() < deadline:
                    current_url = str(self._evaluate(socket, command_id, "location.href") or "")
                    title = str(self._evaluate(socket, command_id + 1, "document.title") or "")
                    body_text = str(
                        self._evaluate(
                            socket,
                            command_id + 2,
                            "document.body ? document.body.innerText.slice(0, 100000) : ''",
                        )
                        or ""
                    )
                    command_id += 3
                    lowered = current_url.lower()
                    if len(body_text.strip()) >= 20 and (
                        "adsmanager" in lowered or "/login" in lowered or "/checkpoint" in lowered
                    ):
                        if "adsmanager" not in lowered or any(
                            marker in body_text
                            for marker in ("Thiết lập để chạy quảng cáo", "Kết quả từ", "Không có chiến dịch")
                        ):
                            break
                    time.sleep(1)
                surface_expression = r"""
                (() => {
                  const clean = value => (value || '').replace(/\s+/g, ' ').trim();
                  let headers = [...document.querySelectorAll('[role="columnheader"]')]
                    .filter(node => node.getClientRects().length)
                    .map(node => clean(node.innerText || node.textContent));
                  let rows = [...document.querySelectorAll('[role="row"]')]
                    .filter(node => node.getClientRects().length)
                    .map(node => [...node.querySelectorAll('[role="gridcell"],td')]
                      .filter(cell => cell.getClientRects().length)
                      .map(cell => clean(cell.innerText || cell.textContent)))
                    .filter(cells => cells.length > 1);
                  if (!headers.length) {
                    headers = [...document.querySelectorAll('table thead th')]
                      .map(node => clean(node.innerText || node.textContent));
                  }
                  if (!rows.length) {
                    rows = [...document.querySelectorAll('table tbody tr')]
                      .map(node => [...node.querySelectorAll('td')]
                        .map(cell => clean(cell.innerText || cell.textContent)))
                      .filter(cells => cells.length > 1);
                  }
                  return {headers, rows};
                })()
                """
                surface = dict(self._evaluate(socket, command_id, surface_expression) or {})
                command_id += 1
                screenshot_result = self._cdp_command(
                    socket,
                    command_id,
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": False},
                )
            screenshot = base64.b64decode(str(screenshot_result["data"]))
            (job_dir / "report.png").write_bytes(screenshot)
            host = (urlparse(current_url).hostname or "").lower()
            lowered_url = current_url.lower()
            lowered_body = body_text.lower()
            authenticated = host.endswith("facebook.com") and not any(
                marker in lowered_url or marker in lowered_body
                for marker in ("/login", "/checkpoint", "đăng nhập facebook", "log in to facebook")
            )
            ads_manager_loaded = "adsmanager" in lowered_url and len(body_text.strip()) >= 20
            account_confirmed = meta_id in current_url or meta_id in body_text
            ready = authenticated and ads_manager_loaded and account_confirmed
            if not authenticated:
                data_state = "login_required"
            elif not ads_manager_loaded:
                data_state = "ads_manager_unavailable"
            elif not account_confirmed:
                data_state = "ad_account_not_confirmed"
            elif "Thiết lập để chạy quảng cáo" in body_text:
                data_state = "requires_account_setup"
            elif "Không có chiến dịch" in body_text:
                data_state = "empty"
            else:
                data_state = "ready"
            metrics = parse_grid(surface, assignment.currency)
            return (
                {
                    "ready": ready,
                    "data_state": data_state,
                    "source": "meta_ads_manager_dom",
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "range_start": assignment.range_start,
                    "range_end": assignment.range_end,
                    "current_url": current_url,
                    "page_title": title,
                    "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                    "metrics": metrics,
                    "safety": {"clicked": False, "ad_mutated": False, "published": False},
                },
                screenshot,
            )
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()


class TelegramReportDelivery:
    def __init__(self, token: str | None):
        self.token = token

    @staticmethod
    def _format(assignment: ReportJobAssignment, result: dict) -> str:
        totals = (result.get("metrics") or {}).get("totals") or {}
        spent = totals.get("amount_spent")
        results = totals.get("results")
        cost = totals.get("cost_per_result")
        format_number = lambda value: "—" if value is None else f"{float(value):,.0f}"
        return "\n".join(
            [
                f"Báo cáo Meta Ads · {assignment.ad_account_label}",
                f"Kỳ: {assignment.range_start} → {assignment.range_end}",
                f"Chi tiêu: {format_number(spent)} {assignment.currency}",
                f"Kết quả: {format_number(results)}",
                f"Chi phí/kết quả: {format_number(cost)} {assignment.currency}",
                f"Chiến dịch đọc được: {int(totals.get('campaigns') or 0)}",
                f"Trạng thái dữ liệu: {result.get('data_state') or 'unknown'}",
            ]
        )

    def send(self, assignment: ReportJobAssignment, result: dict) -> dict:
        delivery = assignment.payload.get("delivery") or {}
        chat_id = str(delivery.get("telegram_chat_id") or "").strip()
        if not chat_id:
            return {"status": "not_requested"}
        if not self.token:
            return {"status": "not_configured", "error": "TELEGRAM_BOT_TOKEN chưa cấu hình trên worker."}
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": chat_id, "text": self._format(assignment, result)},
                timeout=15,
            )
            response.raise_for_status()
            return {"status": "sent"}
        except httpx.HTTPError as exc:
            return {"status": "failed", "error": str(exc)[:500]}


class ReportJobSupervisor:
    def __init__(
        self,
        config: WorkerConfig,
        client: ControlPlaneClient,
        runtime: MetaReportRuntime | None = None,
        delivery: TelegramReportDelivery | None = None,
    ):
        self.client = client
        self.runtime = runtime or MetaReportRuntime(config)
        self.delivery = delivery or TelegramReportDelivery(config.telegram_bot_token)

    def reconcile(self, active_profile_keys: set[str]) -> None:
        assignment = self.client.poll_report_job()
        if assignment is None:
            return
        if assignment.profile_key in active_profile_keys:
            self.client.sync_report_job(
                assignment.job_id,
                status="failed",
                last_error="Chrome profile đang được điều khiển trong browser session.",
            )
            return
        self.client.sync_report_job(assignment.job_id, status="running")
        try:
            result, _screenshot = self.runtime.run(assignment)
            if not result.get("ready"):
                self.client.sync_report_job(
                    assignment.job_id,
                    status="failed",
                    result_json=result,
                    last_error=f"Không thể đọc Ads Manager: {result.get('data_state') or 'unknown'}.",
                )
                return
            result["delivery"] = self.delivery.send(assignment, result)
            self.client.sync_report_job(
                assignment.job_id,
                status="succeeded",
                result_json=result,
            )
        except Exception as exc:
            self.client.sync_report_job(
                assignment.job_id,
                status="failed",
                last_error=str(exc),
            )

