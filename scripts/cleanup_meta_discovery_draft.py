from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from websockets.sync.client import connect

from workers.agent.browser_runtime import (
    BrowserRuntimeManager,
    _build_browser_env,
    _graceful_shutdown_chromium,
)
from workers.agent.config import WorkerConfig
from workers.agent.execution import CampaignPreflightRuntime


CONFIRMATION = "DELETE EXACT DISCOVERY DRAFT"
DELETE_LABELS = ("Bỏ bản nháp", "Xóa bản nháp", "Xóa")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class DiscoveryDraftCleanup(CampaignPreflightRuntime):
    @classmethod
    def _wait(cls, socket, command_id: int, expression: str, timeout: int):
        deadline = time.time() + timeout
        value = None
        while time.time() < deadline:
            value = cls._evaluate(socket, command_id, expression)
            command_id += 1
            if value:
                return command_id, value
            time.sleep(0.5)
        raise RuntimeError(f"Meta UI timeout: {expression[:140]}")

    @classmethod
    def _click_exact(cls, socket, command_id: int, label: str, root_selector: str = "") -> int:
        expression = f"""
        (() => {{
          const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
          const root = {json.dumps(root_selector)}
            ? document.querySelector({json.dumps(root_selector)})
            : document;
          if (!root) return false;
          const nodes = [...root.querySelectorAll('button,[role="button"],[role="menuitem"],div')]
            .filter(node => node.getClientRects().length && normalize(node.innerText || node.textContent) === {json.dumps(label, ensure_ascii=False)});
          const node = nodes.sort((a, b) => a.childElementCount - b.childElementCount)[0];
          if (!node) return false;
          node.click();
          return true;
        }})()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError(f"Không tìm thấy exact action: {label}")
        return command_id + 1

    @classmethod
    def _click_delete_menu_item(cls, socket, command_id: int) -> int:
        expression = r"""
        (() => {
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const node = [...document.querySelectorAll('[role="menuitem"]')]
            .find(item => {
              if (!item.getClientRects().length) return false;
              const text = normalize(item.innerText || item.textContent);
              return text === 'Xóa' || text.startsWith('Xóa ') || text === 'Bỏ bản nháp' || text.startsWith('Bỏ bản nháp ');
            });
          if (!node) return false;
          node.click();
          return true;
        })()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError("Không click được action xóa exact discovery draft trong menu.")
        return command_id + 1

    @classmethod
    def _click_delete_confirmation(cls, socket, command_id: int) -> int:
        expression = r"""
        (() => {
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const nodes = [...document.querySelectorAll('button,[role="button"]')]
            .filter(item => item.getClientRects().length);
          const node = nodes.find(item => {
            const text = normalize(item.innerText || item.textContent);
            return text === 'Xóa' || text.startsWith('Xóa ') || text === 'Bỏ bản nháp' || text.startsWith('Bỏ bản nháp ');
          });
          if (!node) return false;
          node.click();
          return true;
        })()
        """
        if not cls._evaluate(socket, command_id, expression):
            raise RuntimeError("Không click được confirmation xóa exact discovery draft.")
        return command_id + 1

    @classmethod
    def _surface(cls, socket, command_id: int):
        expression = r"""
        (() => ({
          url: location.href,
          body_text: (document.body?.innerText || '').slice(0, 100000),
          controls: [...document.querySelectorAll('button,[role="button"],[role="menuitem"]')]
            .filter(node => node.getClientRects().length)
            .map(node => ({
              text: (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim(),
              aria_label: node.getAttribute('aria-label') || '',
              role: node.getAttribute('role') || ''
            }))
        }))()
        """
        value = cls._evaluate(socket, command_id, expression)
        return command_id + 1, dict(value or {})

    @classmethod
    def _capture(cls, socket, command_id: int):
        result = cls._cdp_command(
            socket,
            command_id,
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": False},
        )
        return command_id + 1, base64.b64decode(str(result["data"]))

    def run(
        self,
        *,
        profile_key: str,
        ad_account_id: str,
        campaign_id: str,
        campaign_name: str,
        output_dir: Path,
        delete: bool,
    ) -> dict:
        if not campaign_name.startswith("[DISCOVERY "):
            raise RuntimeError("Cleanup chỉ chấp nhận campaign_name bắt đầu bằng '[DISCOVERY '.")
        if not campaign_id.isdigit():
            raise RuntimeError("campaign_id phải là Meta numeric ID.")

        browser_config = BrowserRuntimeManager(self.config.data_dir).load_config()
        profile_dir = browser_config.profile_root / profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile không tồn tại.")
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / "runtime"
        run_dir.mkdir(parents=True, exist_ok=True)
        editor_url = (
            "https://adsmanager.facebook.com/adsmanager/manage/campaigns/edit/standalone?"
            + urlencode(
                {
                    "act": ad_account_id.removeprefix("act_"),
                    "selected_campaign_ids": campaign_id,
                }
            )
        )
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
                editor_url,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        result = {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "verified_exact_draft": False,
            "deleted": False,
            "published": False,
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
                guard_expression = f"""
                (() => {{
                  const body = document.body?.innerText || '';
                  return location.href.includes({json.dumps(campaign_id)})
                    && body.includes({json.dumps(campaign_name, ensure_ascii=False)})
                    && body.includes('Bản nháp');
                }})()
                """
                command_id, _ = self._wait(
                    socket,
                    command_id,
                    guard_expression,
                    self.config.execution_timeout_seconds,
                )
                result["verified_exact_draft"] = True
                command_id = self._click_exact(socket, command_id, "Menu hành động")
                time.sleep(1)
                command_id, menu_surface = self._surface(socket, command_id)
                command_id, menu_shot = self._capture(socket, command_id)
                (output_dir / "menu.json").write_text(
                    json.dumps(menu_surface, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "menu.png").write_bytes(menu_shot)
                result["menu_actions"] = [
                    item["text"] for item in menu_surface.get("controls", []) if item.get("text")
                ]
                if not delete:
                    return result

                available = set(result["menu_actions"])
                delete_label = next((label for label in DELETE_LABELS if label in available), None)
                if not delete_label:
                    delete_label = next(
                        (
                            label
                            for label in result["menu_actions"]
                            if label.startswith("Xóa ") or label.startswith("Bỏ bản nháp ")
                        ),
                        None,
                    )
                if not delete_label:
                    raise RuntimeError("Menu của exact draft không có action xóa/bỏ bản nháp đã biết.")
                delete_item_visible = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        "[...document.querySelectorAll('[role=menuitem]')].some(node => node.getClientRects().length && /^(Xóa|Bỏ bản nháp)/.test((node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim()))",
                    )
                )
                command_id += 1
                if not delete_item_visible:
                    command_id = self._click_exact(socket, command_id, "Menu hành động")
                    time.sleep(0.75)
                command_id = self._click_delete_menu_item(socket, command_id)
                time.sleep(1)
                has_dialog = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        "Boolean(document.querySelector('[role=dialog]'))",
                    )
                )
                command_id += 1
                if has_dialog:
                    command_id, dialog_surface = self._surface(socket, command_id)
                    command_id, dialog_shot = self._capture(socket, command_id)
                    (output_dir / "dialog.json").write_text(
                        json.dumps(dialog_surface, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    (output_dir / "dialog.png").write_bytes(dialog_shot)
                    dialog_actions = {
                        item["text"]
                        for item in dialog_surface.get("controls", [])
                        if item.get("text")
                    }
                    confirm_label = next(
                        (label for label in DELETE_LABELS if label in dialog_actions),
                        None,
                    )
                    if not confirm_label:
                        confirm_label = next(
                            (
                                label
                                for label in dialog_actions
                                if label.startswith("Xóa ")
                                or label.startswith("Bỏ bản nháp ")
                            ),
                            None,
                        )
                    if not confirm_label:
                        raise RuntimeError("Dialog xóa không có confirmation label đã biết.")
                    command_id = self._click_delete_confirmation(socket, command_id)
                time.sleep(8)
                list_url = (
                    "https://adsmanager.facebook.com/adsmanager/manage/campaigns?"
                    + urlencode({"act": ad_account_id.removeprefix("act_")})
                )
                self._cdp_command(socket, command_id, "Page.navigate", {"url": list_url})
                command_id += 1
                command_id, _ = self._wait(
                    socket,
                    command_id,
                    "(document.body?.innerText || '').includes('Kết quả từ') || (document.body?.innerText || '').includes('Không có chiến dịch')",
                    self.config.execution_timeout_seconds,
                )
                still_present = bool(
                    self._evaluate(
                        socket,
                        command_id,
                        f"(document.body?.innerText || '').includes({json.dumps(campaign_name, ensure_ascii=False)})",
                    )
                )
                command_id += 1
                if still_present:
                    raise RuntimeError("Meta vẫn còn exact discovery draft sau confirmation xóa.")
                result["deleted"] = True
                return result
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()
            (output_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-key", required=True)
    parser.add_argument("--ad-account-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--campaign-name", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--confirm", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.delete and args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing deletion. Pass --confirm '{CONFIRMATION}'.")
    config = WorkerConfig.from_env()
    result = DiscoveryDraftCleanup(config).run(
        profile_key=args.profile_key,
        ad_account_id=args.ad_account_id,
        campaign_id=args.campaign_id,
        campaign_name=args.campaign_name,
        output_dir=args.output_dir.resolve(),
        delete=args.delete,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
