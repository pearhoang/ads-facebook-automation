from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.parse import parse_qs, urlparse

from websockets.sync.client import connect

from workers.agent.browser_runtime import _build_browser_env, _graceful_shutdown_chromium
from workers.agent.config import WorkerConfig
from workers.agent.execution import CampaignPreflightRuntime, MetaDraftBuildRuntime


CONFIRMATION = "DISCOVER META OBJECTIVES"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class ObjectiveDiscovery(CampaignPreflightRuntime):
    def __init__(self, config: WorkerConfig, output_dir: Path):
        super().__init__(config)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _click_text(cls, socket, command_id: int, text: str, *, dialog_first: bool = False) -> int:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(text, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const root = {str(dialog_first).lower()}
            ? (document.querySelector('[role="dialog"]') || document)
            : document;
          const candidates = [...root.querySelectorAll('button,[role="button"],label,a,div')]
            .filter(node => node.getClientRects().length && normalize(node.innerText || node.textContent) === wanted);
          const node = candidates.sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không tìm thấy control Meta: {text}")
        return command_id + 1

    @classmethod
    def _click_text_startswith(cls, socket, command_id: int, text: str) -> int:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(text, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const node = [...document.querySelectorAll('button,[role="button"],label,div')]
            .filter(item => item.getClientRects().length && normalize(item.innerText || item.textContent).startsWith(wanted))
            .sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không tìm thấy control Meta bắt đầu bằng: {text}")
        return command_id + 1

    @classmethod
    def _set_input(cls, socket, command_id: int, placeholder: str, value: str) -> int:
        expression = f"""
        (() => {{
          const node = [...document.querySelectorAll('input,textarea')]
            .find(item => item.getClientRects().length && (item.placeholder || '').includes({json.dumps(placeholder)}));
          if (!node) return false;
          const prototype = node instanceof HTMLTextAreaElement
            ? HTMLTextAreaElement.prototype
            : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
          setter.call(node, {json.dumps(value, ensure_ascii=False)});
          node.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: null}}));
          node.dispatchEvent(new Event('change', {{bubbles: true}}));
          node.blur();
          return true;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không tìm thấy input Meta: {placeholder}")
        return command_id + 1

    @classmethod
    def _select_objective(cls, socket, command_id: int, index: int) -> int:
        expression = f"""
        (() => {{
          const radios = [...document.querySelectorAll('input[type="radio"]')]
            .filter(node => node.getClientRects().length);
          const target = radios[{index}];
          if (!target) return false;
          target.click();
          return target.checked;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không thể chọn objective radio index={index}.")
        return command_id + 1

    @classmethod
    def _wait(cls, socket, command_id: int, expression: str, timeout: int) -> tuple[int, Any]:
        deadline = time.time() + timeout
        last_value: Any = None
        while time.time() < deadline:
            last_value = cls._evaluate(socket, command_id, expression)
            command_id += 1
            if last_value:
                return command_id, last_value
            time.sleep(0.5)
        raise RuntimeError(f"Meta UI timeout: {expression[:140]}")

    @classmethod
    def _surface(cls, socket, command_id: int) -> tuple[int, dict[str, Any]]:
        expression = r"""
        (() => {
          const visible = node => Boolean(node && node.getClientRects().length);
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const controls = [...document.querySelectorAll('input,textarea,select,button,[role="button"],[role="radio"],[role="combobox"]')]
            .filter(visible)
            .slice(0, 600)
            .map(node => ({
              tag: node.tagName,
              type: node.getAttribute('type') || '',
              role: node.getAttribute('role') || '',
              text: normalize(node.innerText || node.textContent).slice(0, 240),
              placeholder: node.getAttribute('placeholder') || '',
              aria_label: node.getAttribute('aria-label') || '',
              value: 'value' in node ? String(node.value || '').slice(0, 240) : '',
              checked: 'checked' in node ? Boolean(node.checked) : null,
              disabled: Boolean(node.disabled || node.getAttribute('aria-disabled') === 'true')
            }));
          return {
            url: location.href,
            title: document.title,
            body_text: (document.body?.innerText || '').slice(0, 100000),
            controls
          };
        })()
        """
        value = cls._evaluate(socket, command_id, expression)
        return command_id + 1, dict(value or {})

    @classmethod
    def _capture(cls, socket, command_id: int) -> tuple[int, bytes]:
        result = cls._cdp_command(
            socket,
            command_id,
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": False},
        )
        return command_id + 1, base64.b64decode(str(result["data"]))

    def _save_stage(
        self,
        socket,
        command_id: int,
        objective: str,
        stage: str,
    ) -> tuple[int, dict[str, Any]]:
        command_id, surface = self._surface(socket, command_id)
        command_id, screenshot = self._capture(socket, command_id)
        objective_dir = self.output_dir / objective
        objective_dir.mkdir(parents=True, exist_ok=True)
        (objective_dir / f"{stage}.json").write_text(
            json.dumps(surface, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (objective_dir / f"{stage}.png").write_bytes(screenshot)
        return command_id, surface

    @classmethod
    def _navigate(cls, socket, command_id: int, url: str) -> int:
        cls._cdp_command(socket, command_id, "Page.navigate", {"url": url})
        return command_id + 1

    @classmethod
    def _select_exact_draft(cls, socket, command_id: int, campaign_name: str) -> int:
        expression = f"""
        (() => {{
          const wanted = {json.dumps(campaign_name, ensure_ascii=False)};
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const link = [...document.querySelectorAll('a')]
            .find(node => node.getClientRects().length && normalize(node.innerText || node.textContent) === wanted);
          if (!link) return false;
          let container = link;
          for (let depth = 0; depth < 14 && container; depth += 1, container = container.parentElement) {{
            const checkbox = container.querySelector?.('input[type="checkbox"]:not([aria-label])');
            if (checkbox && checkbox.getClientRects().length) {{ checkbox.click(); return true; }}
          }}
          return false;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không thể chọn exact discovery draft: {campaign_name}")
        return command_id + 1

    def _delete_exact_draft(
        self,
        socket,
        command_id: int,
        list_url: str,
        campaign_name: str,
    ) -> int:
        command_id = self._navigate(socket, command_id, list_url)
        command_id, _ = self._wait(
            socket,
            command_id,
            f"[...document.querySelectorAll('a')].some(e => (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim() === {json.dumps(campaign_name, ensure_ascii=False)})",
            self.config.execution_timeout_seconds,
        )
        command_id = self._select_exact_draft(socket, command_id, campaign_name)
        time.sleep(0.75)
        command_id = self._click_text(socket, command_id, "Bỏ bản nháp")
        time.sleep(0.75)
        has_dialog = bool(
            self._evaluate(
                socket,
                command_id,
                "Boolean(document.querySelector('[role=dialog]'))",
            )
        )
        command_id += 1
        if has_dialog:
            command_id = self._click_text(
                socket,
                command_id,
                "Bỏ bản nháp",
                dialog_first=True,
            )
        command_id, _ = self._wait(
            socket,
            command_id,
            f"![...document.querySelectorAll('a')].some(e => (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim() === {json.dumps(campaign_name, ensure_ascii=False)})",
            self.config.execution_timeout_seconds,
        )
        return command_id

    @classmethod
    def _current_campaign_id(cls, socket, command_id: int) -> tuple[int, str]:
        current_url = str(cls._evaluate(socket, command_id, "location.href") or "")
        values = parse_qs(urlparse(current_url).query).get("selected_campaign_ids") or []
        campaign_id = str(values[0]) if values else ""
        if not campaign_id.isdigit():
            raise RuntimeError("Không lấy được Meta campaign ID của discovery draft.")
        return command_id + 1, campaign_id

    @classmethod
    def _delete_current_exact_draft(
        cls,
        socket,
        command_id: int,
        campaign_id: str,
        campaign_name: str,
        timeout_seconds: int,
    ) -> int:
        current_url = str(cls._evaluate(socket, command_id, "location.href") or "")
        command_id += 1
        meta_values = parse_qs(urlparse(current_url).query).get("act") or []
        meta_id = str(meta_values[0]) if meta_values else ""
        if not meta_id.isdigit():
            raise RuntimeError("Không lấy được ad account ID để xác minh cleanup.")
        campaign_editor_url = (
            "https://adsmanager.facebook.com/adsmanager/manage/campaigns/edit/standalone?"
            + urlencode(
                {
                    "act": meta_id,
                    "selected_campaign_ids": campaign_id,
                }
            )
        )
        command_id = cls._navigate(socket, command_id, campaign_editor_url)
        guard = f"""
        (() => {{
          const body = document.body?.innerText || '';
          return location.href.includes({json.dumps(campaign_id)})
            && body.includes({json.dumps(campaign_name, ensure_ascii=False)})
            && body.includes('Bản nháp');
        }})()
        """
        command_id, _ = cls._wait(socket, command_id, guard, timeout_seconds)
        command_id = cls._click_text(socket, command_id, "Menu hành động")
        command_id, _ = cls._wait(
            socket,
            command_id,
            "[...document.querySelectorAll('[role=menuitem]')].some(node => node.getClientRects().length && /^(Xóa|Bỏ bản nháp)/.test((node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim()))",
            timeout_seconds,
        )
        delete_clicked = cls._evaluate(
            socket,
            command_id,
            r"""
            (() => {
              const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
              const node = [...document.querySelectorAll('[role="menuitem"]')]
                .find(item => item.getClientRects().length && /^(Xóa|Bỏ bản nháp)/.test(normalize(item.innerText || item.textContent)));
              if (!node) return false;
              node.click();
              return true;
            })()
            """,
        )
        command_id += 1
        if not delete_clicked:
            raise RuntimeError("Không click được action xóa discovery draft.")
        command_id, _ = cls._wait(
            socket,
            command_id,
            "[...document.querySelectorAll('button,[role=button]')].some(node => node.getClientRects().length && ['Xóa','Bỏ bản nháp'].includes((node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim()))",
            timeout_seconds,
        )
        confirmation_clicked = cls._evaluate(
            socket,
            command_id,
            r"""
            (() => {
              const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
              const node = [...document.querySelectorAll('button,[role="button"]')]
                .find(item => item.getClientRects().length && ['Xóa','Bỏ bản nháp'].includes(normalize(item.innerText || item.textContent)));
              if (!node) return false;
              node.click();
              return true;
            })()
            """,
        )
        command_id += 1
        if not confirmation_clicked:
            raise RuntimeError("Không click được confirmation xóa discovery draft.")
        time.sleep(8)
        list_url = "https://adsmanager.facebook.com/adsmanager/manage/campaigns?" + urlencode(
            {"act": meta_id}
        )
        command_id = cls._navigate(socket, command_id, list_url)
        command_id, _ = cls._wait(
            socket,
            command_id,
            "(document.body?.innerText || '').includes('Kết quả từ') || (document.body?.innerText || '').includes('Không có chiến dịch')",
            timeout_seconds,
        )
        still_present = bool(
            cls._evaluate(
                socket,
                command_id,
                f"(document.body?.innerText || '').includes({json.dumps(campaign_name, ensure_ascii=False)})",
            )
        )
        command_id += 1
        if still_present:
            raise RuntimeError("Meta vẫn còn exact discovery draft sau confirmation xóa.")
        return command_id

    def run(
        self,
        *,
        profile_key: str,
        meta_ad_account_id: str,
        objectives: list[str],
        preserve_campaign_name: str,
        preserve_campaign_id: str,
    ) -> dict[str, Any]:
        browser_config = self.browser_manager.load_config()
        profile_dir = browser_config.profile_root / profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile không tồn tại.")

        meta_id = meta_ad_account_id.removeprefix("act_")
        list_url = "https://adsmanager.facebook.com/adsmanager/manage/campaigns?" + urlencode(
            {"act": meta_id}
        )
        run_dir = self.output_dir / "runtime"
        run_dir.mkdir(parents=True, exist_ok=True)
        env = _build_browser_env(
            base_env=os.environ.copy(),
            display=":0",
            profile_dir=profile_dir,
            session_dir=run_dir,
            chromium_bin=browser_config.chromium_bin,
        )
        log_file = (run_dir / "chromium.log").open("ab")
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
                list_url,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        created_names: list[str] = []
        result: dict[str, Any] = {
            "started_at": datetime.now(UTC).isoformat(),
            "ad_account_id": meta_id,
            "preserve_campaign_name": preserve_campaign_name,
            "objectives": {},
            "cleanup": {},
            "safety": {"draft_only": True, "published": False},
        }
        command_id = 1
        try:
            target = self._wait_for_page()
            with connect(
                str(target["webSocketDebuggerUrl"]),
                open_timeout=5,
                max_size=16 * 1024 * 1024,
            ) as socket:
                self._cdp_command(socket, command_id, "Page.enable")
                command_id += 1
                for objective in objectives:
                    label = MetaDraftBuildRuntime.OBJECTIVE_LABELS[objective]
                    index = MetaDraftBuildRuntime.OBJECTIVE_INDEXES[objective]
                    campaign_name = f"[DISCOVERY {stamp}] {label}"
                    created_names.append(campaign_name)
                    objective_result: dict[str, Any] = {
                        "label": label,
                        "campaign_name": campaign_name,
                        "stages": [],
                    }
                    result["objectives"][objective] = objective_result
                    try:
                        command_id = self._navigate(socket, command_id, list_url)
                        command_id, _ = self._wait(
                            socket,
                            command_id,
                            "[...document.querySelectorAll('button,[role=button]')].some(e => (e.innerText || '').trim() === 'Tạo')",
                            self.config.execution_timeout_seconds,
                        )
                        command_id = self._click_text(socket, command_id, "Tạo")
                        command_id, _ = self._wait(
                            socket,
                            command_id,
                            "(document.body?.innerText || '').includes('Chọn mục tiêu chiến dịch')",
                            self.config.execution_timeout_seconds,
                        )
                        if not (self.output_dir / "objective_modal.json").exists():
                            command_id, modal_surface = self._surface(socket, command_id)
                            command_id, modal_shot = self._capture(socket, command_id)
                            (self.output_dir / "objective_modal.json").write_text(
                                json.dumps(modal_surface, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            (self.output_dir / "objective_modal.png").write_bytes(modal_shot)
                        command_id = self._select_objective(socket, command_id, index)
                        time.sleep(0.5)
                        command_id = self._click_text(socket, command_id, "Tiếp tục")
                        setup_expression = """
                        (() => {
                          if ([...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên chiến dịch'))) return 'editor';
                          if ((document.body?.innerText || '').includes('Chọn cách thiết lập chiến dịch')) return 'setup';
                          return '';
                        })()
                        """
                        command_id, setup_state = self._wait(
                            socket,
                            command_id,
                            setup_expression,
                            self.config.execution_timeout_seconds,
                        )
                        if setup_state == "setup":
                            command_id, _ = self._save_stage(
                                socket,
                                command_id,
                                objective,
                                "setup",
                            )
                            objective_result["stages"].append("setup")
                            manual_label = f"Chiến dịch {label.lower()} thủ công"
                            command_id = self._click_text_startswith(
                                socket,
                                command_id,
                                manual_label,
                            )
                            time.sleep(0.5)
                            command_id = self._click_text(socket, command_id, "Tiếp tục")
                        command_id, _ = self._wait(
                            socket,
                            command_id,
                            "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên chiến dịch'))",
                            self.config.execution_timeout_seconds,
                        )
                        command_id = self._set_input(
                            socket,
                            command_id,
                            "Nhập tên chiến dịch",
                            campaign_name,
                        )
                        time.sleep(1.5)
                        command_id, discovery_campaign_id = self._current_campaign_id(
                            socket,
                            command_id,
                        )
                        objective_result["campaign_id"] = discovery_campaign_id
                        command_id, _ = self._save_stage(socket, command_id, objective, "campaign")
                        objective_result["stages"].append("campaign")

                        command_id = self._click_text(socket, command_id, "Tiếp")
                        command_id, _ = self._wait(
                            socket,
                            command_id,
                            "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên nhóm quảng cáo'))",
                            self.config.execution_timeout_seconds,
                        )
                        command_id = self._set_input(
                            socket,
                            command_id,
                            "Nhập tên nhóm quảng cáo",
                            f"{campaign_name} — Ad Set",
                        )
                        time.sleep(1.5)
                        command_id, _ = self._save_stage(socket, command_id, objective, "adset")
                        objective_result["stages"].append("adset")

                        try:
                            command_id = self._click_text(socket, command_id, "Tiếp")
                            command_id, _ = self._wait(
                                socket,
                                command_id,
                                "[...document.querySelectorAll('input')].some(e => (e.placeholder || '').includes('Nhập tên quảng cáo'))",
                                20,
                            )
                            command_id = self._set_input(
                                socket,
                                command_id,
                                "Nhập tên quảng cáo",
                                f"{campaign_name} — Ad",
                            )
                            time.sleep(1.5)
                            command_id, _ = self._save_stage(socket, command_id, objective, "ad")
                            objective_result["stages"].append("ad")
                        except Exception as exc:
                            objective_result["ad_stage_error"] = str(exc)
                    except Exception as exc:
                        objective_result["error"] = str(exc)
                        try:
                            command_id, error_surface = self._save_stage(
                                socket,
                                command_id,
                                objective,
                                "error",
                            )
                            objective_result["error_url"] = str(
                                error_surface.get("url") or ""
                            )
                            try:
                                command_id, discovery_campaign_id = self._current_campaign_id(
                                    socket,
                                    command_id,
                                )
                                objective_result["campaign_id"] = discovery_campaign_id
                            except Exception:
                                pass
                        except Exception as capture_exc:
                            objective_result["error_capture"] = str(capture_exc)
                    finally:
                        try:
                            discovery_campaign_id = str(
                                objective_result.get("campaign_id") or ""
                            )
                            if not discovery_campaign_id:
                                result["cleanup"][campaign_name] = "not_created"
                                continue
                            command_id = self._delete_current_exact_draft(
                                socket,
                                command_id,
                                discovery_campaign_id,
                                campaign_name,
                                self.config.execution_timeout_seconds,
                            )
                            result["cleanup"][campaign_name] = "deleted"
                        except Exception as cleanup_exc:
                            result["cleanup"][campaign_name] = f"failed: {cleanup_exc}"

                preserve_url = (
                    "https://adsmanager.facebook.com/adsmanager/manage/campaigns/edit/standalone?"
                    + urlencode(
                        {
                            "act": meta_id,
                            "selected_campaign_ids": preserve_campaign_id,
                        }
                    )
                )
                command_id = self._navigate(socket, command_id, preserve_url)
                command_id, _ = self._wait(
                    socket,
                    command_id,
                    f"location.href.includes({json.dumps(preserve_campaign_id)}) && (document.body?.innerText || '').includes({json.dumps(preserve_campaign_name, ensure_ascii=False)}) && (document.body?.innerText || '').includes('Bản nháp')",
                    self.config.execution_timeout_seconds,
                )
                command_id, final_surface = self._surface(socket, command_id)
                command_id, final_shot = self._capture(socket, command_id)
                (self.output_dir / "final_list.json").write_text(
                    json.dumps(final_surface, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (self.output_dir / "final_list.png").write_bytes(final_shot)
                body = str(final_surface.get("body_text") or "")
                result["preserved_campaign_present"] = (
                    preserve_campaign_name in body and preserve_campaign_id in str(final_surface.get("url") or "")
                )
                result["discovery_drafts_remaining"] = [
                    name
                    for name in created_names
                    if result["cleanup"].get(name) not in {"deleted", "not_created"}
                ]
                result["finished_at"] = datetime.now(UTC).isoformat()
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()
            (self.output_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Khảo sát Meta objective bằng unpublished drafts và xóa exact discovery drafts sau mỗi lượt."
    )
    parser.add_argument("--profile-key", required=True)
    parser.add_argument("--ad-account-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--objectives",
        nargs="+",
        choices=list(MetaDraftBuildRuntime.OBJECTIVE_LABELS),
        default=list(MetaDraftBuildRuntime.OBJECTIVE_LABELS),
    )
    parser.add_argument(
        "--preserve-campaign-name",
        default="Chiến dịch Mức độ nhận biết",
    )
    parser.add_argument("--preserve-campaign-id", required=True)
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing mutation. Pass --confirm '{CONFIRMATION}'.")
    config = WorkerConfig.from_env()
    discovery = ObjectiveDiscovery(config, args.output_dir.resolve())
    result = discovery.run(
        profile_key=args.profile_key,
        meta_ad_account_id=args.ad_account_id,
        objectives=list(args.objectives),
        preserve_campaign_name=args.preserve_campaign_name,
        preserve_campaign_id=args.preserve_campaign_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    cleanup_failures = [
        value
        for value in result["cleanup"].values()
        if value not in {"deleted", "not_created"}
    ]
    if cleanup_failures or result.get("discovery_drafts_remaining"):
        raise SystemExit(2)
    if not result.get("preserved_campaign_present"):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
