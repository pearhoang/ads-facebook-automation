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

from scripts.cleanup_meta_discovery_draft import DiscoveryDraftCleanup
from workers.agent.browser_runtime import (
    BrowserRuntimeManager,
    _build_browser_env,
    _graceful_shutdown_chromium,
)
from workers.agent.config import WorkerConfig


CONFIRMATION = "DELETE EXACT META DRAFT"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class ExactMetaDraftCleanup(DiscoveryDraftCleanup):
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
        if not campaign_id.isdigit():
            raise RuntimeError("campaign_id phải là Meta numeric ID.")
        if not campaign_name.strip():
            raise RuntimeError("campaign_name không được để trống.")

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
            "verified_absent_by_id": False,
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
                command_id, before_surface = self._surface(socket, command_id)
                command_id, before_shot = self._capture(socket, command_id)
                (output_dir / "before.json").write_text(
                    json.dumps(before_surface, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "before.png").write_bytes(before_shot)
                if not delete:
                    return result

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
                    item["text"]
                    for item in menu_surface.get("controls", [])
                    if item.get("text")
                ]
                if not any(
                    label == "Xóa"
                    or label.startswith("Xóa ")
                    or label == "Bỏ bản nháp"
                    or label.startswith("Bỏ bản nháp ")
                    for label in result["menu_actions"]
                ):
                    raise RuntimeError("Exact draft không có action xóa/bỏ bản nháp đã biết.")
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
                    command_id = self._click_delete_confirmation(socket, command_id)
                time.sleep(8)

                self._cdp_command(socket, command_id, "Page.navigate", {"url": editor_url})
                command_id += 1
                time.sleep(8)
                still_exact_draft = bool(
                    self._evaluate(socket, command_id, guard_expression)
                )
                command_id += 1
                if still_exact_draft:
                    raise RuntimeError("Meta vẫn mở được exact draft ID sau confirmation xóa.")
                command_id, after_surface = self._surface(socket, command_id)
                command_id, after_shot = self._capture(socket, command_id)
                (output_dir / "after.json").write_text(
                    json.dumps(after_surface, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (output_dir / "after.png").write_bytes(after_shot)
                result["deleted"] = True
                result["verified_absent_by_id"] = True
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
    result = ExactMetaDraftCleanup(WorkerConfig.from_env()).run(
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
