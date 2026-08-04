from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

from websockets.sync.client import connect

from .browser_runtime import (
    BrowserRuntimeManager,
    _build_browser_env,
    _graceful_shutdown_chromium,
)
from .config import WorkerConfig
from .contracts import ExecutionJobAssignment
from .control_plane import ControlPlaneClient
from .meta_fields import FieldAction, action_blocks, build_stage_plan


class CampaignPreflightRuntime:
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.browser_manager = BrowserRuntimeManager(config.data_dir)

    @staticmethod
    def _cdp_command(socket, command_id: int, method: str, params: dict | None = None) -> dict:
        socket.send(json.dumps({"id": command_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(socket.recv())
            if message.get("id") == command_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} failed: {message['error']}")
                return dict(message.get("result") or {})

    @classmethod
    def _evaluate(cls, socket, command_id: int, expression: str) -> Any:
        result = cls._cdp_command(
            socket,
            command_id,
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return result.get("result", {}).get("value")

    def _wait_for_page(self) -> dict:
        deadline = time.time() + self.config.execution_timeout_seconds
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urlopen(
                    f"http://127.0.0.1:{self.config.execution_debug_port}/json/list",
                    timeout=3,
                ) as response:
                    tabs = json.loads(response.read().decode("utf-8"))
                pages = [item for item in tabs if item.get("type") == "page"]
                if pages:
                    return pages[0]
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            time.sleep(0.5)
        raise RuntimeError("Chromium preflight did not expose a page target.") from last_error

    def run(self, assignment: ExecutionJobAssignment) -> tuple[dict, bytes]:
        browser_config = self.browser_manager.load_config()
        profile_dir = browser_config.profile_root / assignment.profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile does not exist on worker.")
        job_dir = self.config.data_dir / "execution-jobs" / assignment.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        meta_id = assignment.meta_ad_account_id.removeprefix("act_")
        start_url = "https://business.facebook.com/adsmanager/manage/campaigns?" + urlencode(
            {"act": meta_id}
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
                "--window-size=1440,900",
                f"--remote-debugging-port={self.config.execution_debug_port}",
                start_url,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            target = self._wait_for_page()
            with connect(str(target["webSocketDebuggerUrl"]), open_timeout=5, max_size=8 * 1024 * 1024) as socket:
                self._cdp_command(socket, 1, "Page.enable")
                deadline = time.time() + self.config.execution_timeout_seconds
                current_url = ""
                title = ""
                body_text = ""
                command_id = 2
                while time.time() < deadline:
                    current_url = str(self._evaluate(socket, command_id, "location.href") or "")
                    title = str(self._evaluate(socket, command_id + 1, "document.title") or "")
                    body_text = str(
                        self._evaluate(
                            socket,
                            command_id + 2,
                            "document.body ? document.body.innerText.slice(0, 20000) : ''",
                        )
                        or ""
                    )
                    command_id += 3
                    lowered_url = current_url.lower()
                    if len(body_text.strip()) >= 20 and (
                        "adsmanager" in lowered_url
                        or "/login" in lowered_url
                        or "/checkpoint" in lowered_url
                    ):
                        break
                    time.sleep(1)
                screenshot_result = self._cdp_command(
                    socket,
                    command_id,
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": False},
                )
            screenshot = base64.b64decode(str(screenshot_result["data"]))
            host = (urlparse(current_url).hostname or "").lower()
            lowered_url = current_url.lower()
            lowered_body = body_text.lower()
            page_has_content = len(body_text.strip()) >= 20
            login_markers = ("/login", "/checkpoint", "đăng nhập facebook", "log in to facebook")
            authenticated = host.endswith("facebook.com") and not any(
                marker in lowered_url or marker in lowered_body for marker in login_markers
            )
            ads_manager_loaded = "adsmanager" in lowered_url and page_has_content
            account_confirmed = meta_id in current_url or meta_id in body_text
            ready = authenticated and ads_manager_loaded and account_confirmed
            if not authenticated:
                readiness = "login_required"
            elif not ads_manager_loaded:
                readiness = "ads_manager_unavailable"
            elif not account_confirmed:
                readiness = "ad_account_not_confirmed"
            else:
                readiness = "ready"
            return (
                {
                    "readiness": readiness,
                    "ready": ready,
                    "authenticated": authenticated,
                    "ads_manager_loaded": ads_manager_loaded,
                    "page_has_content": page_has_content,
                    "ad_account_confirmed": account_confirmed,
                    "current_url": current_url,
                    "page_title": title,
                    "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                    "safety": {"clicked": False, "published": False},
                },
                screenshot,
            )
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()


class MetaDraftBuildRuntime(CampaignPreflightRuntime):
    OBJECTIVE_LABELS = {
        "awareness": "Mức độ nhận biết",
        "traffic": "Lưu lượng truy cập",
        "engagement": "Lượt tương tác",
        "leads": "Khách hàng tiềm năng",
        "app_promotion": "Quảng cáo ứng dụng",
        "sales": "Doanh số",
    }
    OBJECTIVE_INDEXES = {
        "awareness": 0,
        "traffic": 1,
        "engagement": 2,
        "leads": 3,
        "app_promotion": 4,
        "sales": 5,
    }
    LEGACY_ADAPTERS = {
        "awareness": {
            "setup_mode": "direct",
            "required_fields": ["targeting.page_name", "creative.primary_text"],
        },
        "traffic": {
            "setup_mode": "manual",
            "manual_setup_label": "Chiến dịch lưu lượng truy cập thủ công",
            "required_fields": [
                "targeting.page_name",
                "creative.primary_text",
                "creative.destination_url",
            ],
        },
        "engagement": {
            "setup_mode": "direct",
            "required_fields": [
                "targeting.page_name",
                "targeting.messaging_destination",
                "creative.primary_text",
            ],
        },
        "leads": {
            "setup_mode": "direct",
            "required_fields": [
                "targeting.page_name",
                "creative.lead_form_name",
                "creative.primary_text",
            ],
        },
        "app_promotion": {
            "setup_mode": "direct",
            "required_fields": [
                "targeting.page_name",
                "targeting.app_name",
                "creative.primary_text",
            ],
        },
        "sales": {
            "setup_mode": "direct",
            "required_fields": [
                "targeting.page_name",
                "creative.primary_text",
                "creative.destination_url",
            ],
        },
    }
    LEGACY_FIELD_ACTIONS = {
        "awareness": [
            {"field_path": "targeting.page_name", "stage": "adset", "handler": "page_exact"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
        "traffic": [
            {"field_path": "targeting.page_name", "stage": "ad", "handler": "page_exact"},
            {"field_path": "creative.destination_url", "stage": "ad", "handler": "destination_url"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
        "engagement": [
            {"field_path": "targeting.page_name", "stage": "ad", "handler": "page_exact"},
            {"field_path": "targeting.messaging_destination", "stage": "ad", "handler": "messaging_destination"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
        "leads": [
            {"field_path": "targeting.page_name", "stage": "adset", "handler": "page_exact"},
            {"field_path": "creative.lead_form_name", "stage": "ad", "handler": "lead_form"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
        "app_promotion": [
            {"field_path": "targeting.app_name", "stage": "adset", "handler": "app_name"},
            {"field_path": "targeting.page_name", "stage": "ad", "handler": "page_exact"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
        "sales": [
            {"field_path": "targeting.page_name", "stage": "ad", "handler": "page_exact"},
            {"field_path": "creative.destination_url", "stage": "ad", "handler": "destination_url"},
            {"field_path": "creative.primary_text", "stage": "ad", "handler": "primary_text"},
        ],
    }
    DEFAULT_FIELD_LABELS = {
        "targeting.countries": "quốc gia targeting",
        "targeting.age_min": "tuổi tối thiểu",
        "targeting.age_max": "tuổi tối đa",
        "targeting.placements": "vị trí quảng cáo",
        "targeting.page_name": "Page Facebook",
        "targeting.messaging_destination": "kênh nhận tin nhắn",
        "targeting.app_name": "ứng dụng",
        "creative.primary_text": "primary text",
        "creative.destination_url": "destination URL",
        "creative.lead_form_name": "Instant Form",
        "creative.headline": "headline",
        "creative.cta": "CTA",
        "creative.asset_local_path": "creative asset",
        "targeting.app_store_country": "quốc gia cửa hàng ứng dụng",
        "targeting.dataset_name": "Pixel/dataset",
        "targeting.conversion_event": "conversion event",
    }

    @classmethod
    def _wait_for_expression(
        cls,
        socket,
        command_id: int,
        expression: str,
        timeout_seconds: int,
    ) -> tuple[int, Any]:
        deadline = time.time() + timeout_seconds
        last_value: Any = None
        while time.time() < deadline:
            last_value = cls._evaluate(socket, command_id, expression)
            command_id += 1
            if last_value:
                return command_id, last_value
            time.sleep(0.5)
        raise RuntimeError(f"Meta UI timeout while waiting for: {expression[:120]}")

    @classmethod
    def _click_text(cls, socket, command_id: int, text: str) -> int:
        expression = rf"""
        (() => {{
          const wanted = {json.dumps(text)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const candidates = [...document.querySelectorAll('button,[role="button"],[role="option"],label,a,div')]
            .filter(node => node.getClientRects().length && normalize(node.innerText || node.textContent) === wanted);
          const node = candidates.sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        clicked = cls._evaluate(socket, command_id, expression)
        if not clicked:
            raise RuntimeError(f"Không tìm thấy control Meta: {text}")
        return command_id + 1

    @classmethod
    def _click_text_startswith(cls, socket, command_id: int, text: str) -> int:
        expression = rf"""
        (() => {{
          const wanted = {json.dumps(text)};
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const candidates = [...document.querySelectorAll('button,[role="button"],label,div')]
            .filter(node => node.getClientRects().length && normalize(node.innerText || node.textContent).startsWith(wanted));
          const node = candidates.sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        clicked = cls._evaluate(socket, command_id, expression)
        if not clicked:
            raise RuntimeError(f"Không tìm thấy control Meta bắt đầu bằng: {text}")
        return command_id + 1

    @classmethod
    def _set_input_by_placeholder(
        cls,
        socket,
        command_id: int,
        placeholder: str,
        value: str,
    ) -> int:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(placeholder)};
          const node = [...document.querySelectorAll('input,textarea')]
            .find(item => item.getClientRects().length && (item.placeholder || '').includes(wanted));
          if (!node) return false;
          const prototype = node instanceof HTMLTextAreaElement
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
          setter.call(node, {json.dumps(value)});
          node.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: null}}));
          node.dispatchEvent(new Event('change', {{bubbles: true}}));
          node.blur();
          return true;
        }})()
        """
        changed = cls._evaluate(socket, command_id, expression)
        if not changed:
            raise RuntimeError(f"Không tìm thấy input Meta: {placeholder}")
        return command_id + 1

    @classmethod
    def _capture(cls, socket, command_id: int) -> tuple[int, bytes]:
        result = cls._cdp_command(
            socket,
            command_id,
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": False},
        )
        return command_id + 1, base64.b64decode(str(result["data"]))

    @classmethod
    def _select_objective_radio(
        cls,
        socket,
        command_id: int,
        objective_index: int,
    ) -> int:
        expression = f"""
        (() => {{
          const radios = [...document.querySelectorAll('input[type="radio"]')]
            .filter(node => node.getClientRects().length);
          const target = radios[{objective_index}];
          if (!target) return false;
          target.click();
          return target.checked;
        }})()
        """
        selected = cls._evaluate(socket, command_id, expression)
        if not selected:
            raise RuntimeError("Không thể chọn objective trong modal tạo campaign.")
        return command_id + 1

    @classmethod
    def _open_existing_draft(
        cls,
        socket,
        command_id: int,
        candidate_names: list[str],
    ) -> int:
        expression = f"""
        (() => {{
          const names = {json.dumps(candidate_names, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const links = [...document.querySelectorAll('a')]
            .filter(node => node.getClientRects().length)
            .filter(node => names.includes(normalize(node.innerText || node.textContent)))
            .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
          const link = links[0];
          if (!link) return false;
          let container = link;
          for (let depth = 0; depth < 12 && container; depth += 1, container = container.parentElement) {{
            const checkbox = container.querySelector?.('input[type="checkbox"]:not([aria-label])');
            if (checkbox) {{ checkbox.click(); return true; }}
          }}
          // Meta's virtualized grid renders the campaign cell and selection cell in
          // separate DOM branches. Match their visual row centers when no common
          // ancestor exists; the first exact-name row is the newest visible draft.
          const linkRect = link.getBoundingClientRect();
          const rowCheckbox = [...document.querySelectorAll('input[type="checkbox"]')]
            .filter(node => !node.getAttribute('aria-label') && node.getClientRects().length);
          const aligned = rowCheckbox
            .map(node => ({{node, rect: node.getBoundingClientRect()}}))
            .filter(item => Math.abs((item.rect.top + item.rect.height / 2) - (linkRect.top + linkRect.height / 2)) <= 18)
            .sort((a, b) => Math.abs(a.rect.left - linkRect.left) - Math.abs(b.rect.left - linkRect.left));
          if (aligned[0]) {{ aligned[0].node.click(); return true; }}
          const fallback = rowCheckbox;
          if (fallback.length !== 1) return false;
          fallback[0].click();
          return true;
        }})()
        """
        selected = cls._evaluate(socket, command_id, expression)
        if not selected:
            raise RuntimeError("Không thể chọn đúng Meta draft để resume.")
        time.sleep(0.75)
        return cls._click_text(socket, command_id + 1, "Chỉnh sửa")

    @classmethod
    def _body(cls, socket, command_id: int) -> tuple[int, str]:
        body = str(
            cls._evaluate(
                socket,
                command_id,
                "document.body ? document.body.innerText.slice(0, 50000) : ''",
            )
            or ""
        )
        return command_id + 1, body

    @classmethod
    def _rewind_editor(cls, socket, command_id: int) -> int:
        expression = r"""
        (() => {
          const visible = node => Boolean(node && node.getClientRects().length);
          const candidates = [...document.querySelectorAll('*')]
            .filter(visible)
            .filter(node => node.scrollHeight > node.clientHeight + 120)
            .filter(node => ['auto', 'scroll'].includes(getComputedStyle(node).overflowY))
            .filter(node => node.clientWidth >= 400 && node.clientHeight >= 300)
            .sort((a, b) => (b.clientWidth * b.clientHeight) - (a.clientWidth * a.clientHeight));
          if (candidates[0]) candidates[0].scrollTop = 0;
          else window.scrollTo(0, 0);
          return true;
        })()
        """
        cls._evaluate(socket, command_id, expression)
        return command_id + 1

    @classmethod
    def _scroll_editor_down(cls, socket, command_id: int) -> tuple[int, bool]:
        expression = r"""
        (() => {
          const visible = node => Boolean(node && node.getClientRects().length);
          const candidates = [...document.querySelectorAll('*')]
            .filter(visible)
            .filter(node => node.scrollHeight > node.clientHeight + 120)
            .filter(node => ['auto', 'scroll'].includes(getComputedStyle(node).overflowY))
            .filter(node => node.clientWidth >= 400 && node.clientHeight >= 300)
            .sort((a, b) => (b.clientWidth * b.clientHeight) - (a.clientWidth * a.clientHeight));
          const target = candidates[0] || document.scrollingElement;
          if (!target) return false;
          const before = target.scrollTop;
          target.scrollTop = Math.min(
            target.scrollTop + 560,
            Math.max(0, target.scrollHeight - target.clientHeight)
          );
          return target.scrollTop > before;
        })()
        """
        moved = bool(cls._evaluate(socket, command_id, expression))
        return command_id + 1, moved

    @classmethod
    def _set_input_by_placeholders(
        cls,
        socket,
        command_id: int,
        placeholders: list[str],
        value: str,
    ) -> tuple[int, str]:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(placeholders, ensure_ascii=False)}
            .map(item => item.toLocaleLowerCase());
          const visible = node => Boolean(node && node.getClientRects().length);
          const controls = [...document.querySelectorAll('input,textarea')].filter(visible);
          const node = controls.find(item => {{
            const descriptor = `${{item.placeholder || ''}} ${{item.getAttribute('aria-label') || ''}}`
              .toLocaleLowerCase();
            return wanted.some(label => descriptor.includes(label));
          }});
          if (!node) return 'not_available';
          if (String(node.value || '').trim() === {json.dumps(value)}) return 'already_set';
          const prototype = node instanceof HTMLTextAreaElement
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
          if (!setter) return 'failed';
          setter.call(node, {json.dumps(value, ensure_ascii=False)});
          node.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: null}}));
          node.dispatchEvent(new Event('change', {{bubbles: true}}));
          node.blur();
          return 'applied';
        }})()
        """
        status = str(cls._evaluate(socket, command_id, expression) or "failed")
        command_id += 1
        if status != "not_available":
            return command_id, status
        command_id = cls._rewind_editor(socket, command_id)
        time.sleep(0.35)
        for _ in range(12):
            status = str(cls._evaluate(socket, command_id, expression) or "failed")
            command_id += 1
            if status != "not_available":
                return command_id, status
            command_id, moved = cls._scroll_editor_down(socket, command_id)
            if not moved:
                break
            time.sleep(0.35)
        return command_id, "not_available"

    @classmethod
    def _set_editable_by_labels(
        cls,
        socket,
        command_id: int,
        labels: list[str],
        value: str,
    ) -> tuple[int, str]:
        expression = f"""
        (() => {{
          const labels = {json.dumps(labels, ensure_ascii=False)}
            .map(item => item.toLocaleLowerCase());
          const visible = node => Boolean(node && node.getClientRects().length);
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const editables = [...document.querySelectorAll(
            'input,textarea,[contenteditable="true"],[role="textbox"]'
          )].filter(visible);
          let node = editables.find(item => {{
            const descriptor = `${{item.placeholder || ''}} ${{item.getAttribute('aria-label') || ''}}`
              .toLocaleLowerCase();
            return labels.some(label => descriptor.includes(label));
          }});
          if (!node) {{
            const anchors = [...document.querySelectorAll('label,span,div,p')]
              .filter(visible)
              .filter(item => {{
                const text = normalize(item.innerText || item.textContent).toLocaleLowerCase();
                return labels.some(label => text === label || text.startsWith(`${{label}} `));
              }})
              .sort((a, b) => a.childElementCount - b.childElementCount);
            for (const anchor of anchors) {{
              let container = anchor;
              for (let depth = 0; depth < 5 && container; depth += 1, container = container.parentElement) {{
                node = [...container.querySelectorAll(
                  'input,textarea,[contenteditable="true"],[role="textbox"]'
                )].find(visible);
                if (node) break;
              }}
              if (node) break;
            }}
          }}
          if (!node) return 'not_available';
          const current = 'value' in node ? String(node.value || '') : normalize(node.textContent);
          if (current.trim() === {json.dumps(value)}) return 'already_set';
          if (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement) {{
            const prototype = node instanceof HTMLTextAreaElement
              ? HTMLTextAreaElement.prototype
              : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
            if (!setter) return 'failed';
            setter.call(node, {json.dumps(value, ensure_ascii=False)});
          }} else {{
            node.focus();
            node.textContent = {json.dumps(value, ensure_ascii=False)};
          }}
          node.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: null}}));
          node.dispatchEvent(new Event('change', {{bubbles: true}}));
          node.blur();
          return 'applied';
        }})()
        """
        status = str(cls._evaluate(socket, command_id, expression) or "failed")
        command_id += 1
        if status != "not_available":
            return command_id, status
        command_id = cls._rewind_editor(socket, command_id)
        time.sleep(0.35)
        for _ in range(12):
            status = str(cls._evaluate(socket, command_id, expression) or "failed")
            command_id += 1
            if status != "not_available":
                return command_id, status
            command_id, moved = cls._scroll_editor_down(socket, command_id)
            if not moved:
                break
            time.sleep(0.35)
        return command_id, "not_available"

    @classmethod
    def _open_control_near_labels(
        cls,
        socket,
        command_id: int,
        labels: list[str],
    ) -> tuple[int, bool]:
        expression = f"""
        (() => {{
          const labels = {json.dumps(labels, ensure_ascii=False)}
            .map(item => item.toLocaleLowerCase());
          const visible = node => Boolean(node && node.getClientRects().length);
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const controls = [...document.querySelectorAll('[role="combobox"],button,[role="button"]')]
            .filter(visible);
          let control = controls.find(item => {{
            const descriptor = `${{normalize(item.innerText || item.textContent)}} ${{item.getAttribute('aria-label') || ''}}`
              .toLocaleLowerCase();
            return labels.some(label => descriptor === label || descriptor.startsWith(`${{label}} `));
          }});
          if (!control) {{
            const anchors = [...document.querySelectorAll('label,span,div,p')]
              .filter(visible)
              .filter(item => {{
                const text = normalize(item.innerText || item.textContent).toLocaleLowerCase();
                return labels.some(label => text === label || text.startsWith(`${{label}} `));
              }})
              .sort((a, b) => a.childElementCount - b.childElementCount);
            for (const anchor of anchors) {{
              let container = anchor;
              for (let depth = 0; depth < 5 && container; depth += 1, container = container.parentElement) {{
                control = [...container.querySelectorAll('[role="combobox"],button,[role="button"]')]
                  .find(visible);
                if (control) break;
              }}
              if (control) break;
            }}
          }}
          if (!control) return false;
          control.click();
          return true;
        }})()
        """
        opened = bool(cls._evaluate(socket, command_id, expression))
        command_id += 1
        if opened:
            return command_id, True
        command_id = cls._rewind_editor(socket, command_id)
        time.sleep(0.35)
        for _ in range(12):
            opened = bool(cls._evaluate(socket, command_id, expression))
            command_id += 1
            if opened:
                return command_id, True
            command_id, moved = cls._scroll_editor_down(socket, command_id)
            if not moved:
                break
            time.sleep(0.35)
        return command_id, False

    @classmethod
    def _try_click_exact(cls, socket, command_id: int, text: str) -> tuple[int, bool]:
        expression = rf"""
        (() => {{
          const wanted = {json.dumps(text, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const node = [...document.querySelectorAll(
            '[role="option"],[role="radio"],button,[role="button"],label,div'
          )]
            .filter(item => item.getClientRects().length)
            .filter(item => normalize(item.innerText || item.textContent) === wanted)
            .sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        clicked = bool(cls._evaluate(socket, command_id, expression))
        return command_id + 1, clicked

    @classmethod
    def _click_point(
        cls,
        socket,
        command_id: int,
        point: dict | None,
    ) -> tuple[int, bool]:
        if not point:
            return command_id, False
        x = float(point.get("x") or 0)
        y = float(point.get("y") or 0)
        if x <= 0 or y <= 0:
            return command_id, False
        cls._cdp_command(
            socket,
            command_id,
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
        )
        command_id += 1
        cls._cdp_command(
            socket,
            command_id,
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
        )
        return command_id + 1, True

    @classmethod
    def _try_click_exact_point(
        cls,
        socket,
        command_id: int,
        text: str,
    ) -> tuple[int, bool]:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(text, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const nodes = [...document.querySelectorAll(
            '[role="option"],[role="menuitem"],button,[role="button"],label,div'
          )]
            .filter(node => !node.disabled && node.getAttribute('aria-disabled') !== 'true')
            .filter(node => {{
              const rect = node.getBoundingClientRect();
              return rect.width > 0 && rect.height > 0 && rect.bottom > 0
                && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
            }})
            .filter(node => normalize(node.innerText || node.textContent) === wanted)
            .sort((a, b) => a.childElementCount - b.childElementCount);
          const node = nodes[0];
          if (!node) return null;
          const rect = node.getBoundingClientRect();
          return {{x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}};
        }})()
        """
        point = cls._evaluate(socket, command_id, expression)
        return cls._click_point(socket, command_id + 1, point)

    @classmethod
    def _set_file_via_native_chooser(
        cls,
        socket,
        command_id: int,
        button_text: str,
        path: Path,
    ) -> tuple[int, bool]:
        cls._cdp_command(
            socket,
            command_id,
            "Page.setInterceptFileChooserDialog",
            {"enabled": True},
        )
        command_id += 1
        expression = f"""
        (() => {{
          const wanted = {json.dumps(button_text, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const node = [...document.querySelectorAll('button,[role="button"],div')]
            .filter(item => {{
              const rect = item.getBoundingClientRect();
              return rect.width > 0 && rect.height > 0 && rect.bottom > 0
                && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth;
            }})
            .filter(item => normalize(item.innerText || item.textContent) === wanted)
            .sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return null;
          const rect = node.getBoundingClientRect();
          return {{x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}};
        }})()
        """
        point = cls._evaluate(socket, command_id, expression)
        command_id += 1
        if not point:
            cls._cdp_command(
                socket,
                command_id,
                "Page.setInterceptFileChooserDialog",
                {"enabled": False},
            )
            return command_id + 1, False
        x = float(point["x"])
        y = float(point["y"])
        cls._cdp_command(
            socket,
            command_id,
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
        )
        command_id += 1
        release_id = command_id
        socket.send(
            json.dumps(
                {
                    "id": release_id,
                    "method": "Input.dispatchMouseEvent",
                    "params": {
                        "type": "mouseReleased",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1,
                    },
                }
            )
        )
        response_seen = False
        backend_node_id: int | None = None
        deadline = time.time() + 8
        while time.time() < deadline and (not response_seen or backend_node_id is None):
            try:
                message = json.loads(socket.recv(timeout=max(0.1, deadline - time.time())))
            except TimeoutError:
                break
            if message.get("id") == release_id:
                if "error" in message:
                    raise RuntimeError(f"CDP file chooser click failed: {message['error']}")
                response_seen = True
            elif message.get("method") == "Page.fileChooserOpened":
                backend_node_id = int((message.get("params") or {}).get("backendNodeId") or 0) or None
        command_id += 1
        if backend_node_id is None:
            cls._cdp_command(
                socket,
                command_id,
                "Page.setInterceptFileChooserDialog",
                {"enabled": False},
            )
            return command_id + 1, False
        cls._cdp_command(
            socket,
            command_id,
            "DOM.setFileInputFiles",
            {"files": [str(path)], "backendNodeId": backend_node_id},
        )
        command_id += 1
        cls._cdp_command(
            socket,
            command_id,
            "Page.setInterceptFileChooserDialog",
            {"enabled": False},
        )
        return command_id + 1, True

    @classmethod
    def _select_exact_near_labels(
        cls,
        socket,
        command_id: int,
        labels: list[str],
        value: str,
    ) -> tuple[int, str]:
        command_id, body = cls._body(socket, command_id)
        if value in body and not any(label in body for label in labels):
            return command_id, "already_set"
        command_id, opened = cls._open_control_near_labels(
            socket,
            command_id,
            labels,
        )
        if not opened:
            return command_id, "not_available"
        time.sleep(0.5)
        command_id, clicked = cls._try_click_exact(socket, command_id, value)
        if not clicked:
            return command_id, "failed"
        time.sleep(0.5)
        return command_id, "applied"

    @classmethod
    def _apply_page_exact(
        cls,
        socket,
        command_id: int,
        page_name: str,
        page_external_id: str,
        timeout_seconds: int,
    ) -> tuple[int, str]:
        command_id = cls._rewind_editor(socket, command_id)
        time.sleep(0.35)
        selected_expression = f"""
        (() => {{
          const name = {json.dumps(page_name, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          return [...document.querySelectorAll('[role="combobox"],button,[aria-haspopup="listbox"]')]
            .filter(node => node.getClientRects().length)
            .some(node => {{
              const text = normalize(node.innerText || node.textContent);
              return text.includes(name);
            }});
        }})()
        """
        if page_name and bool(cls._evaluate(socket, command_id, selected_expression)):
            command_id += 1
            return command_id, "already_set"
        command_id += 1
        command_id, body = cls._body(socket, command_id)
        if "Chọn Trang" not in body:
            return command_id, "not_available"
        command_id = cls._click_text(socket, command_id, "Chọn Trang")
        time.sleep(0.75)
        command_id, body = cls._body(socket, command_id)
        if page_name not in body:
            group_expression = r"""
            (() => {
              const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
              const nodes = [...document.querySelectorAll('div,span')]
                .filter(node => node.getClientRects().length)
                .filter(node => /^Cá nhân(?:\s+\d+\s+trang)?$/.test(normalize(node.innerText || node.textContent)));
              const candidates = [];
              for (const node of nodes) {
                let current = node;
                for (let depth = 0; depth < 5 && current; depth += 1, current = current.parentElement) {
                  const text = normalize(current.innerText || current.textContent);
                  const rect = current.getBoundingClientRect();
                  if (/^Cá nhân\s+\d+\s+trang$/.test(text) && rect.width >= 240 && rect.height >= 28 && rect.height <= 90) {
                    candidates.push({area: rect.width * rect.height, x: rect.right - 20, y: rect.top + rect.height / 2});
                  }
                }
              }
              candidates.sort((a,b) => a.area - b.area);
              return candidates[0] || null;
            })()
            """
            point = cls._evaluate(socket, command_id, group_expression)
            command_id += 1
            command_id, expanded = cls._click_point(socket, command_id, point)
            if not expanded:
                return command_id, "failed"
        try:
            command_id, _ = cls._wait_for_expression(
                socket,
                command_id,
                (
                    f"(document.body?.innerText || '').includes({json.dumps(page_name)})"
                    + (
                        f" && (document.body?.innerText || '').includes({json.dumps(page_external_id)})"
                        if page_external_id
                        else ""
                    )
                ),
                timeout_seconds,
            )
        except RuntimeError:
            return command_id, "failed"
        option_expression = f"""
        (() => {{
          const name = {json.dumps(page_name, ensure_ascii=False)};
          const externalId = {json.dumps(page_external_id)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const candidates = [];
          for (const node of [...document.querySelectorAll('div,span,label,[role="option"]')]) {{
            if (!node.getClientRects().length || normalize(node.innerText || node.textContent) !== name) continue;
            let current = node;
            for (let depth = 0; depth < 6 && current; depth += 1, current = current.parentElement) {{
              const text = normalize(current.innerText || current.textContent);
              const rect = current.getBoundingClientRect();
              if (text.includes(name) && (!externalId || text.includes(externalId)) && rect.width >= 240 && rect.height >= 28 && rect.height <= 140) {{
                candidates.push({{area: rect.width * rect.height, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}});
              }}
            }}
          }}
          candidates.sort((a,b) => a.area - b.area);
          return candidates[0] || null;
        }})()
        """
        point = cls._evaluate(socket, command_id, option_expression)
        command_id += 1
        command_id, clicked = cls._click_point(socket, command_id, point)
        if not clicked:
            return command_id, "failed"
        time.sleep(1)
        selected = bool(cls._evaluate(socket, command_id, selected_expression))
        return command_id + 1, "applied" if selected else "failed"

    @classmethod
    def _set_file_input(
        cls,
        socket,
        command_id: int,
        local_path: str,
    ) -> tuple[int, str]:
        path = Path(local_path).resolve()
        if not path.is_file():
            return command_id, "failed"
        is_video = path.suffix.lower() in {".mp4", ".mov"}
        media_word = "video" if is_video else "image"

        def find_input(next_command_id: int) -> tuple[int, str | None]:
            expression = f"""
            (() => {{
              const mediaWord = {json.dumps(media_word)};
              const inputs = [...document.querySelectorAll('input[type="file"]')];
              return inputs.find(node => {{
                const accept = (node.accept || '').toLocaleLowerCase();
                return !accept || accept.includes(mediaWord) || accept.includes('*/*');
              }}) || null;
            }})()
            """
            result = cls._cdp_command(
                socket,
                next_command_id,
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": False},
            )
            object_id = result.get("result", {}).get("objectId")
            return next_command_id + 1, str(object_id) if object_id else None

        command_id, object_id = find_input(command_id)
        chooser_selected = False
        if not object_id:
            command_id, setup_clicked = cls._try_click_exact_point(
                socket,
                command_id,
                "Thiết lập nội dung",
            )
            if setup_clicked:
                time.sleep(0.75)
                media_setup_label = "Quảng cáo video" if is_video else "Quảng cáo hình ảnh"
                command_id, media_setup_clicked = cls._try_click_exact_point(
                    socket,
                    command_id,
                    media_setup_label,
                )
                if media_setup_clicked:
                    time.sleep(1)
                    command_id, object_id = find_input(command_id)
                    if not object_id:
                        command_id, chooser_selected = cls._set_file_via_native_chooser(
                            socket,
                            command_id,
                            "Tải lên",
                            path,
                        )
                        if chooser_selected:
                            time.sleep(3)
        if not object_id and not chooser_selected:
            labels = (
                ["Thêm video", "Tải video lên", "Tải lên"]
                if is_video
                else ["Thêm hình ảnh", "Tải hình ảnh lên", "Tải lên"]
            )
            labels += ["Thêm file phương tiện", "Thêm nội dung đa phương tiện"]
            for label in labels:
                command_id, clicked = cls._try_click_exact(socket, command_id, label)
                if clicked:
                    time.sleep(0.75)
                    command_id, object_id = find_input(command_id)
                    if object_id:
                        break
        if not object_id and not chooser_selected:
            return command_id, "not_available"
        if object_id:
            cls._cdp_command(
                socket,
                command_id,
                "DOM.setFileInputFiles",
                {"files": [str(path)], "objectId": object_id},
            )
            command_id += 1
            time.sleep(2)
            selected = bool(
                cls._evaluate(
                    socket,
                    command_id,
                    f"[...document.querySelectorAll('input[type=\"file\"]')].some(node => [...(node.files || [])].some(file => file.name === {json.dumps(path.name)}))",
                )
            )
            command_id += 1
        else:
            selected = chooser_selected
        if not selected:
            return command_id, "failed"
        # Media is only committed after Meta's picker advances. This is not the
        # final Review/Publish button; it only confirms the selected asset.
        for _ in range(20):
            command_id, advanced = cls._try_click_exact(socket, command_id, "Tiếp")
            if advanced:
                time.sleep(1)
                break
            time.sleep(0.5)
        return command_id, "applied" if advanced else "failed"

    @classmethod
    def _apply_countries_exact(
        cls,
        socket,
        command_id: int,
        value: str,
    ) -> tuple[int, str]:
        labels = {
            "VN": "Việt Nam",
            "US": "Hoa Kỳ",
            "TH": "Thái Lan",
            "SG": "Singapore",
            "MY": "Malaysia",
            "ID": "Indonesia",
            "PH": "Philippines",
        }
        countries = [
            labels.get(item.strip().upper(), item.strip())
            for item in value.split(",")
            if item.strip()
        ]
        command_id, body = cls._body(socket, command_id)
        if countries and all(country in body for country in countries):
            return command_id, "already_set"
        if len(countries) != 1:
            return command_id, "not_available"
        # Meta lazy-renders the Audience controls. The selected country may only
        # appear after scrolling even though it is already the effective value.
        command_id = cls._rewind_editor(socket, command_id)
        time.sleep(0.35)
        for _ in range(12):
            command_id, body = cls._body(socket, command_id)
            if all(country in body for country in countries):
                return command_id, "already_set"
            command_id, moved = cls._scroll_editor_down(socket, command_id)
            if not moved:
                break
            time.sleep(0.35)
        return cls._select_exact_near_labels(
            socket,
            command_id,
            ["bao gồm vị trí", "vị trí đối tượng", "vị trí địa lý", "địa điểm"],
            countries[0],
        )

    @classmethod
    def _apply_field_action(
        cls,
        socket,
        command_id: int,
        action: FieldAction,
        spec: dict,
        timeout_seconds: int,
    ) -> tuple[int, dict]:
        if not action.value:
            status = "blocked" if action.required and action.terminal else "skipped"
            detail = "Thiếu giá trị trong approved snapshot." if action.required else "Không cấu hình."
            return command_id, action.as_result(status, detail)

        handler = action.handler
        status = "not_available"
        if handler == "page_exact":
            command_id, status = cls._apply_page_exact(
                socket,
                command_id,
                action.value,
                str((spec.get("targeting") or {}).get("page_external_id") or "").strip(),
                timeout_seconds,
            )
        elif handler == "countries_exact":
            command_id, status = cls._apply_countries_exact(
                socket,
                command_id,
                action.value,
            )
        elif handler == "age_min":
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["độ tuổi tối thiểu", "tuổi tối thiểu"],
                action.value,
            )
        elif handler == "age_max":
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["độ tuổi tối đa", "tuổi tối đa"],
                action.value,
            )
        elif handler == "placements":
            command_id, body = cls._body(socket, command_id)
            status = (
                "already_set"
                if action.value == "advantage_plus" and "Advantage+ đang bật" in body
                else "not_available"
            )
        elif handler == "media_upload":
            command_id, status = cls._set_file_input(
                socket,
                command_id,
                action.value,
            )
        elif handler == "destination_url":
            command_id, status = cls._set_input_by_placeholders(
                socket,
                command_id,
                ["nhập url của đích đến", "url trang web", "website url"],
                action.value,
            )
        elif handler == "app_name":
            command_id, status = cls._set_input_by_placeholders(
                socket,
                command_id,
                ["nhập tên ứng dụng", "id ứng dụng", "url chính xác trên cửa hàng"],
                action.value,
            )
            if status in {"applied", "already_set"}:
                time.sleep(0.75)
                command_id, clicked = cls._try_click_exact(socket, command_id, action.value)
                if not clicked:
                    status = "failed"
        elif handler == "app_store_country":
            command_id, status = cls._set_input_by_placeholders(
                socket,
                command_id,
                ["quốc gia trên cửa hàng", "quốc gia có ứng dụng"],
                action.value,
            )
        elif handler == "primary_text":
            command_id, status = cls._set_editable_by_labels(
                socket,
                command_id,
                ["văn bản chính", "nội dung chính", "primary text"],
                action.value,
            )
            if status == "not_available":
                command_id, text_tab_clicked = cls._try_click_exact(
                    socket,
                    command_id,
                    "Văn bản",
                )
                if text_tab_clicked:
                    time.sleep(0.75)
                    command_id, status = cls._set_editable_by_labels(
                        socket,
                        command_id,
                        ["văn bản chính", "nội dung chính", "primary text"],
                        action.value,
                    )
        elif handler == "headline":
            command_id, status = cls._set_editable_by_labels(
                socket,
                command_id,
                ["tiêu đề", "headline"],
                action.value,
            )
        elif handler == "cta":
            cta_labels = {
                "LEARN_MORE": "Tìm hiểu thêm",
                "SHOP_NOW": "Mua ngay",
                "SIGN_UP": "Đăng ký",
                "CONTACT_US": "Liên hệ",
            }
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["nút kêu gọi hành động", "kêu gọi hành động", "cta"],
                cta_labels.get(action.value, action.value),
            )
        elif handler == "messaging_destination":
            destination_labels = {
                "messenger": "Messenger",
                "instagram": "Instagram",
                "whatsapp": "WhatsApp",
            }
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["ứng dụng nhắn tin", "đích đến của tin nhắn", "kênh nhắn tin"],
                destination_labels.get(action.value.lower(), action.value),
            )
        elif handler == "lead_form":
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["mẫu phản hồi tức thì", "biểu mẫu"],
                action.value,
            )
        elif handler == "dataset":
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["tập dữ liệu", "bộ dữ liệu", "pixel"],
                action.value,
            )
        elif handler == "conversion_event":
            command_id, status = cls._select_exact_near_labels(
                socket,
                command_id,
                ["sự kiện chuyển đổi", "conversion event"],
                action.value,
            )

        detail_by_status = {
            "applied": "Đã điền/chọn và phát sự kiện thay đổi.",
            "already_set": "Control đã có đúng giá trị.",
            "not_available": "Control chưa xuất hiện ở stage này.",
            "failed": "Control xuất hiện nhưng không xác nhận được giá trị.",
        }
        return command_id, action.as_result(
            status,
            detail_by_status.get(status, "Không xác định được trạng thái control."),
        )

    @classmethod
    def _apply_stage_fields(
        cls,
        socket,
        command_id: int,
        adapter: dict,
        spec: dict,
        stage: str,
        timeout_seconds: int,
        field_labels: dict[str, str],
    ) -> tuple[int, list[dict], list[str]]:
        results: list[dict] = []
        blockers: list[str] = []
        for action in build_stage_plan(adapter, spec, stage):
            scan_attempts = 12 if stage == "ad" else 1
            if stage == "ad":
                command_id = cls._rewind_editor(socket, command_id)
                time.sleep(0.35)
            for attempt in range(scan_attempts):
                try:
                    command_id, result = cls._apply_field_action(
                        socket,
                        command_id,
                        action,
                        spec,
                        timeout_seconds,
                    )
                except RuntimeError as exc:
                    result = action.as_result("failed", str(exc))
                if result["status"] != "not_available" or attempt + 1 >= scan_attempts:
                    break
                command_id, moved = cls._scroll_editor_down(socket, command_id)
                if not moved:
                    break
                time.sleep(0.35)
            results.append(result)
            if action_blocks(result):
                label = field_labels.get(action.field_path, action.field_path)
                blockers.append(
                    f"Không thể áp dụng {label} tại {stage}: {result['detail']}"
                )
        return command_id, results, blockers

    @classmethod
    def _verify_default_surface(
        cls,
        body: str,
        adapter: dict,
    ) -> tuple[list[dict], list[str]]:
        results: list[dict] = []
        blockers: list[str] = []
        checks = (
            ("adapter.default_conversion_location", adapter.get("conversion_location_label")),
            ("adapter.performance_goal", adapter.get("performance_goal_label")),
        )
        for field_path, raw_label in checks:
            label = str(raw_label or "").strip()
            if not label:
                continue
            status = "verified" if label in body else "not_available"
            results.append(
                {
                    "field_path": field_path,
                    "stage": "adset",
                    "handler": "surface_text",
                    "required": True,
                    "terminal": True,
                    "status": status,
                    "detail": "Đúng default path đã khảo sát." if status == "verified" else "Không thấy label default trong Meta UI.",
                }
            )
            if status != "verified":
                blockers.append(f"Meta UI không khớp adapter: thiếu '{label}'.")
        return results, blockers

    def run(self, assignment: ExecutionJobAssignment) -> tuple[dict, dict[str, bytes]]:
        safety = assignment.payload.get("safety") or {}
        if safety.get("allow_click") is not True or safety.get("allow_publish") is not False:
            raise RuntimeError("Draft builder refused an invalid safety contract.")
        spec = assignment.payload.get("draft_spec") or {}
        campaign_name = str(spec.get("campaign_name") or "").strip()
        if not campaign_name:
            raise RuntimeError("Draft spec is missing campaign_name.")
        objective = str(spec.get("objective") or "").strip()
        objective_label = self.OBJECTIVE_LABELS.get(objective)
        if not objective_label:
            raise RuntimeError(f"Objective is not supported by Meta draft builder: {objective}")
        objective_index = self.OBJECTIVE_INDEXES[objective]
        adapter = dict(
            assignment.payload.get("objective_adapter")
            or self.LEGACY_ADAPTERS.get(objective)
            or {}
        )
        if not adapter.get("field_actions"):
            adapter["field_actions"] = list(self.LEGACY_FIELD_ACTIONS.get(objective) or [])
        field_labels = {
            **self.DEFAULT_FIELD_LABELS,
            **dict(adapter.get("field_labels") or {}),
        }
        targeting = spec.get("targeting") or {}
        creative = spec.get("creative") or {}
        currency = str(assignment.payload.get("ad_account", {}).get("currency") or "VND")
        budget_minor = int(spec.get("daily_budget_minor") or 0)
        budget_value = budget_minor if currency in {"VND", "JPY", "KRW"} else budget_minor / 100

        browser_config = self.browser_manager.load_config()
        profile_dir = browser_config.profile_root / assignment.profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile does not exist on worker.")
        job_dir = self.config.data_dir / "execution-jobs" / assignment.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        meta_id = assignment.meta_ad_account_id.removeprefix("act_")
        start_url = "https://adsmanager.facebook.com/adsmanager/manage/campaigns?" + urlencode(
            {"act": meta_id}
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
                "--window-size=1440,900",
                f"--remote-debugging-port={self.config.execution_debug_port}",
                start_url,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        artifacts: dict[str, bytes] = {}
        checkpoints: list[str] = []
        blockers: list[str] = []
        field_results: list[dict] = []
        budget_applied = False
        published = False
        try:
            target = self._wait_for_page()
            with connect(
                str(target["webSocketDebuggerUrl"]),
                open_timeout=5,
                max_size=16 * 1024 * 1024,
            ) as socket:
                command_id = 1
                self._cdp_command(socket, command_id, "Page.enable")
                command_id += 1
                command_id, _ = self._wait_for_expression(
                    socket,
                    command_id,
                    "[...document.querySelectorAll('button,[role=button]')].some(e => (e.innerText || '').trim() === 'Tạo')",
                    self.config.execution_timeout_seconds,
                )
                # The toolbar is rendered before Meta finishes populating the campaign table.
                # Wait for either the approved campaign name or a terminal table marker so a
                # retry cannot race the list and create a duplicate draft.
                command_id, _ = self._wait_for_expression(
                    socket,
                    command_id,
                    (
                        f"(document.body?.innerText || '').includes({json.dumps(campaign_name, ensure_ascii=False)})"
                        " || (document.body?.innerText || '').includes('Kết quả từ')"
                        " || (document.body?.innerText || '').includes('Không có chiến dịch')"
                    ),
                    self.config.execution_timeout_seconds,
                )
                # Meta exposes the result-count marker before virtualized rows are
                # attached. Give the table a short stabilization window before the
                # exact-name check; otherwise a retry can create a duplicate.
                time.sleep(4)
                resumed_existing = False
                matching_draft = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        f"[...document.querySelectorAll('a')].some(node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim() === {json.dumps(campaign_name)})",
                    )
                )
                command_id += 1
                if matching_draft:
                    resumed_existing = True
                    command_id = self._open_existing_draft(
                        socket,
                        command_id,
                        [campaign_name],
                    )
                    command_id, _ = self._wait_for_expression(
                        socket,
                        command_id,
                        "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên chiến dịch'))",
                        self.config.execution_timeout_seconds,
                    )
                else:
                    command_id = self._click_text(socket, command_id, "Tạo")
                    create_state_expression = """
                (() => {
                  if ([...document.querySelectorAll('input')].some(
                    e => (e.placeholder || '').includes('Nhập tên chiến dịch')
                  )) return 'editor';
                  const body = document.body?.innerText || '';
                  if (body.includes('Tạo chiến dịch mới') && body.includes('Chọn mục tiêu chiến dịch')) {
                    return 'objective_modal';
                  }
                  if (body.includes('Thiết lập để chạy quảng cáo') &&
                      body.includes('Đi đến phần Tổng quan về tài khoản')) return 'account_setup';
                  return '';
                })()
                """
                    command_id, create_state = self._wait_for_expression(
                        socket,
                        command_id,
                        create_state_expression,
                        self.config.execution_timeout_seconds,
                    )
                    if create_state == "objective_modal":
                        command_id = self._select_objective_radio(
                            socket, command_id, objective_index
                        )
                        time.sleep(0.75)
                        command_id = self._click_text(socket, command_id, "Tiếp tục")
                        setup_state_expression = """
                        (() => {
                          if ([...document.querySelectorAll('input')].some(
                            e => (e.placeholder || '').includes('Nhập tên chiến dịch')
                          )) return 'editor';
                          if ((document.body?.innerText || '').includes('Chọn cách thiết lập chiến dịch')) {
                            return 'setup';
                          }
                          return '';
                        })()
                        """
                        command_id, setup_state = self._wait_for_expression(
                            socket,
                            command_id,
                            setup_state_expression,
                            self.config.execution_timeout_seconds,
                        )
                        if setup_state == "setup":
                            if adapter.get("setup_mode") != "manual":
                                raise RuntimeError(
                                    f"Meta hiển thị setup trung gian ngoài adapter của objective {objective}."
                                )
                            manual_setup_label = str(
                                adapter.get("manual_setup_label")
                                or f"Chiến dịch {objective_label.lower()} thủ công"
                            )
                            command_id = self._click_text_startswith(
                                socket,
                                command_id,
                                manual_setup_label,
                            )
                            time.sleep(0.5)
                            command_id = self._click_text(socket, command_id, "Tiếp tục")
                        command_id, _ = self._wait_for_expression(
                            socket,
                            command_id,
                            "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên chiến dịch'))",
                            self.config.execution_timeout_seconds,
                        )
                    if create_state == "account_setup":
                        command_id, artifacts["failure"] = self._capture(socket, command_id)
                        return (
                            {
                                "readiness": "awaiting_user",
                                "ready": False,
                                "phase": "account_setup",
                                "checkpoints": [],
                                "blockers": [
                                    "Meta yêu cầu hoàn tất Tổng quan tài khoản: thêm phương thức thanh toán và Page Facebook."
                                ],
                                "current_url": str(
                                    self._evaluate(socket, command_id, "location.href") or ""
                                ),
                                "objective": objective,
                                "objective_adapter": adapter,
                                "field_results": field_results,
                                "safety": {"clicked": True, "published": False},
                            },
                            artifacts,
                        )
                command_id = self._set_input_by_placeholder(
                    socket, command_id, "Nhập tên chiến dịch", campaign_name
                )
                # The objective picker is part of the create flow only. On resume Meta
                # opens the Campaign editor directly and the objective is immutable.
                if not resumed_existing:
                    command_id = self._click_text(socket, command_id, objective_label)
                    time.sleep(1)
                command_id, campaign_budget_status = self._set_input_by_placeholders(
                    socket,
                    command_id,
                    ["vui lòng nhập số tiền"],
                    str(budget_value),
                )
                field_results.append(
                    {
                        "field_path": "campaign.daily_budget",
                        "stage": "campaign",
                        "handler": "budget",
                        "required": True,
                        "terminal": False,
                        "status": campaign_budget_status,
                        "detail": "Đã xử lý budget ở Campaign." if campaign_budget_status in {"applied", "already_set"} else "Budget không nằm ở Campaign cho objective này.",
                    }
                )
                budget_applied = campaign_budget_status in {"applied", "already_set"}
                command_id, artifacts["campaign_step"] = self._capture(socket, command_id)
                checkpoints.append("campaign")

                command_id = self._click_text(socket, command_id, "Tiếp")
                command_id, _ = self._wait_for_expression(
                    socket,
                    command_id,
                    "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên nhóm quảng cáo'))",
                    self.config.execution_timeout_seconds,
                )
                command_id = self._set_input_by_placeholder(
                    socket,
                    command_id,
                    "Nhập tên nhóm quảng cáo",
                    str(spec.get("adset_name") or f"{campaign_name} — Ad Set"),
                )
                expected_goal = str(adapter.get("performance_goal_label") or "").strip()
                if expected_goal:
                    try:
                        command_id, _ = self._wait_for_expression(
                            socket,
                            command_id,
                            f"(document.body?.innerText || '').includes({json.dumps(expected_goal)})",
                            self.config.execution_timeout_seconds,
                        )
                    except RuntimeError:
                        pass
                command_id, adset_body = self._body(socket, command_id)
                surface_results, surface_blockers = self._verify_default_surface(
                    adset_body,
                    adapter,
                )
                field_results.extend(surface_results)
                blockers.extend(surface_blockers)
                command_id, adset_results, adset_blockers = self._apply_stage_fields(
                    socket,
                    command_id,
                    adapter,
                    spec,
                    "adset",
                    self.config.execution_timeout_seconds,
                    field_labels,
                )
                field_results.extend(adset_results)
                blockers.extend(adset_blockers)
                if budget_applied:
                    adset_budget_status = "skipped"
                else:
                    command_id, adset_budget_status = self._set_input_by_placeholders(
                        socket,
                        command_id,
                        ["vui lòng nhập số tiền"],
                        str(budget_value),
                    )
                field_results.append(
                    {
                        "field_path": "campaign.daily_budget",
                        "stage": "adset",
                        "handler": "budget",
                        "required": True,
                        "terminal": True,
                        "status": adset_budget_status,
                        "detail": (
                            "Đã xử lý budget ở Ad Set."
                            if adset_budget_status in {"applied", "already_set"}
                            else "Budget đã được xử lý ở Campaign."
                            if adset_budget_status == "skipped"
                            else "Budget không nằm ở Ad Set cho objective này."
                        ),
                    }
                )
                budget_applied = budget_applied or adset_budget_status in {
                    "applied",
                    "already_set",
                }
                if not budget_applied:
                    blockers.append("Không tìm thấy control budget ở Campaign hoặc Ad Set.")
                command_id, artifacts["adset_step"] = self._capture(socket, command_id)
                checkpoints.append("adset")
                if blockers:
                    return (
                        {
                            "readiness": "awaiting_user",
                            "ready": False,
                            "phase": "adset",
                            "checkpoints": checkpoints,
                            "blockers": blockers,
                            "current_url": str(self._evaluate(socket, command_id, "location.href") or ""),
                            "objective": objective,
                            "objective_adapter": adapter,
                            "field_results": field_results,
                            "safety": {"clicked": True, "published": False},
                        },
                        artifacts,
                    )

                command_id = self._click_text(socket, command_id, "Tiếp")
                command_id, _ = self._wait_for_expression(
                    socket,
                    command_id,
                    "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên quảng cáo'))",
                    self.config.execution_timeout_seconds,
                )
                command_id = self._set_input_by_placeholder(
                    socket,
                    command_id,
                    "Nhập tên quảng cáo",
                    str(spec.get("ad_name") or f"{campaign_name} — Ad"),
                )
                command_id, ad_results, ad_blockers = self._apply_stage_fields(
                    socket,
                    command_id,
                    adapter,
                    spec,
                    "ad",
                    self.config.execution_timeout_seconds,
                    field_labels,
                )
                field_results.extend(ad_results)
                blockers.extend(ad_blockers)
                # The media picker advances to the Text step. Persist the whole
                # creative by advancing the remaining modal steps before treating
                # the background Publish button as the Review boundary.
                wizard_advanced = False
                for _ in range(4):
                    command_id, advanced = self._try_click_exact_point(socket, command_id, "Xong")
                    if not advanced:
                        command_id, advanced = self._try_click_exact_point(
                            socket,
                            command_id,
                            "Tiếp",
                        )
                    if not advanced:
                        break
                    wizard_advanced = True
                    time.sleep(1.5)
                wizard_open = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        "[...document.querySelectorAll('button,[role=button]')].some(node => node.getClientRects().length && ['Tiếp','Xong'].includes((node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim()))",
                    )
                )
                command_id += 1
                field_results.append(
                    {
                        "field_path": "creative.content_wizard",
                        "stage": "ad",
                        "handler": "content_wizard",
                        "required": True,
                        "terminal": True,
                        "status": "failed" if wizard_open else "applied" if wizard_advanced else "already_set",
                        "detail": (
                            "Modal Thiết lập nội dung vẫn đang mở."
                            if wizard_open
                            else "Đã hoàn tất modal Thiết lập nội dung."
                            if wizard_advanced
                            else "Không còn modal Thiết lập nội dung cần hoàn tất."
                        ),
                    }
                )
                if wizard_open:
                    blockers.append("Chưa hoàn tất modal Thiết lập nội dung của creative.")
                command_id, ad_body = self._body(socket, command_id)
                error_match = re.search(r"Xem lại\s+(\d+)\s+lỗi", ad_body)
                if error_match:
                    blockers.append(f"Meta đang báo {error_match.group(1)} lỗi cần xử lý trong draft.")
                command_id, artifacts["ad_step"] = self._capture(socket, command_id)
                checkpoints.append("ad")
                publish_visible = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        "[...document.querySelectorAll('button,[role=button]')].some(e => (e.innerText || '').trim() === 'Đăng')",
                    )
                )
                command_id += 1
                if not publish_visible:
                    blockers.append("Chưa đến được review boundary có nút Đăng.")
                artifacts["review_step"] = artifacts["ad_step"]
                if blockers:
                    return (
                        {
                            "readiness": "awaiting_user",
                            "ready": False,
                            "phase": "ad",
                            "checkpoints": checkpoints,
                            "blockers": blockers,
                            "current_url": str(
                                self._evaluate(socket, command_id, "location.href") or ""
                            ),
                            "objective": objective,
                            "objective_adapter": adapter,
                            "field_results": field_results,
                            "safety": {"clicked": True, "published": False},
                        },
                        artifacts,
                    )
                return (
                    {
                        "readiness": "review_ready",
                        "ready": True,
                        "phase": "review",
                        "checkpoints": checkpoints,
                        "blockers": [],
                        "current_url": str(self._evaluate(socket, command_id, "location.href") or ""),
                        "objective": objective,
                        "objective_adapter": adapter,
                        "field_results": field_results,
                        "safety": {"clicked": True, "published": published},
                    },
                    artifacts,
                )
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()


class ExecutionJobSupervisor:
    def __init__(
        self,
        config: WorkerConfig,
        client: ControlPlaneClient,
        runtime: CampaignPreflightRuntime | None = None,
        draft_runtime: MetaDraftBuildRuntime | None = None,
    ):
        self.config = config
        self.client = client
        self.runtime = runtime or CampaignPreflightRuntime(config)
        self.draft_runtime = draft_runtime or MetaDraftBuildRuntime(config)

    def _notify_telegram(self, assignment: ExecutionJobAssignment, message: str) -> None:
        request_meta = assignment.payload.get("automation_request") or {}
        if not request_meta or not self.config.telegram_bot_token:
            return
        title = str(request_meta.get("title") or "Công việc quảng cáo")
        request_id = str(request_meta.get("id") or "")[:8]
        text = f"{title}\n{message}\nMã công việc: {request_id}"
        for chat_id in self.config.telegram_allowed_users:
            try:
                body = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
                with urlopen(
                    f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
                    data=body,
                    timeout=10,
                ) as response:
                    response.read()
            except (HTTPError, URLError, TimeoutError, OSError):
                # Delivery is fail-soft; control-plane timeline remains canonical.
                continue

    def _prepare_creative_asset(self, assignment: ExecutionJobAssignment) -> None:
        draft_spec = assignment.payload.get("draft_spec") or {}
        creative = draft_spec.get("creative") or {}
        asset_id = str(creative.get("asset_id") or "").strip()
        if not asset_id:
            return
        snapshot = creative.get("asset_snapshot") or {}
        if str(snapshot.get("id") or "") != asset_id:
            raise RuntimeError("Creative asset snapshot does not match asset_id.")
        expected_sha256 = str(snapshot.get("sha256") or "").strip().lower()
        if len(expected_sha256) != 64:
            raise RuntimeError("Creative asset snapshot is missing SHA-256.")
        suffix = Path(str(snapshot.get("file_name") or "")).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}:
            raise RuntimeError("Creative asset snapshot has an unsupported extension.")
        asset_root = (self.config.data_dir / "execution-assets" / assignment.job_id).resolve()
        target = (asset_root / f"{asset_id}{suffix}").resolve()
        target.relative_to(asset_root)
        self.client.download_execution_asset(
            assignment.job_id,
            asset_id,
            target,
            expected_sha256,
        )
        creative["asset_local_path"] = str(target)
        draft_spec["creative"] = creative
        assignment.payload["draft_spec"] = draft_spec

    def reconcile(self, active_profile_keys: set[str]) -> None:
        assignment = self.client.poll_execution_job()
        if assignment is None:
            return
        if assignment.profile_key in active_profile_keys:
            self.client.sync_execution_job(
                assignment.job_id,
                status="awaiting_user",
                last_error="Chrome profile đang được điều khiển trong browser session.",
            )
            return
        self.client.sync_execution_job(assignment.job_id, status="running")
        self._notify_telegram(
            assignment,
            "Worker đã bắt đầu preflight."
            if assignment.payload.get("safety", {}).get("mode") != "draft_only"
            else "Worker đang điền Campaign → Ad Set → Ad; publish vẫn bị khóa.",
        )
        try:
            if assignment.payload.get("safety", {}).get("mode") == "draft_only":
                self._prepare_creative_asset(assignment)
                result, artifacts = self.draft_runtime.run(assignment)
                for kind, content in artifacts.items():
                    self.client.upload_execution_artifact(assignment.job_id, kind, content)
            else:
                result, screenshot = self.runtime.run(assignment)
                self.client.upload_execution_screenshot(assignment.job_id, screenshot)
            if result.get("ready"):
                self.client.sync_execution_job(
                    assignment.job_id,
                    status="succeeded",
                    result_json=result,
                )
                self._notify_telegram(
                    assignment,
                    "Preflight đạt, hệ thống đang tự chuyển sang draft builder."
                    if assignment.payload.get("safety", {}).get("mode") != "draft_only"
                    else "Đã điền xong và dừng tại Review. Chưa publish quảng cáo.",
                )
            else:
                self.client.sync_execution_job(
                    assignment.job_id,
                    status="awaiting_user",
                    result_json=result,
                    last_error=(
                        "Meta draft cần người dùng hoàn thiện field còn thiếu qua noVNC."
                        if assignment.payload.get("safety", {}).get("mode") == "draft_only"
                        else "Preflight cần người dùng kiểm tra đăng nhập hoặc quyền ad account."
                    ),
                )
                self._notify_telegram(
                    assignment,
                    "Meta đang cần login/2FA/challenge hoặc còn field chưa thể tự xác định. Hãy mở Tài khoản Facebook khi sẵn sàng.",
                )
        except Exception as exc:
            self.client.sync_execution_job(
                assignment.job_id,
                status="failed",
                last_error=str(exc),
            )
            self._notify_telegram(
                assignment,
                "Worker gặp lỗi và đã chuyển cho cơ chế recovery/checkpoint xử lý; bạn không cần tạo lại yêu cầu.",
            )
