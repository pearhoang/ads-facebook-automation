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

from workers.agent.browser_runtime import _build_browser_env, _graceful_shutdown_chromium
from workers.agent.config import WorkerConfig
from workers.agent.execution import CampaignPreflightRuntime


CONFIRMATION = "INSPECT META DRAFT FIELDS READ ONLY"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class DraftFieldInspector(CampaignPreflightRuntime):
    @classmethod
    def _scroll_editor_down(cls, socket, command_id: int) -> tuple[int, dict]:
        expression = r"""
        (() => {
          const visible = node => Boolean(node && node.getClientRects().length);
          const candidates = [...document.querySelectorAll('*')]
            .filter(visible)
            .filter(node => node.scrollHeight > node.clientHeight + 120)
            .filter(node => {
              const style = getComputedStyle(node);
              return ['auto', 'scroll'].includes(style.overflowY);
            })
            .map(node => ({
              node,
              area: node.clientWidth * node.clientHeight,
              before: node.scrollTop,
              max: node.scrollHeight - node.clientHeight
            }))
            .filter(item => item.node.clientWidth >= 400 && item.node.clientHeight >= 300)
            .sort((a, b) => b.area - a.area);
          const target = candidates[0];
          if (!target) {
            const before = document.scrollingElement?.scrollTop || 0;
            window.scrollBy(0, 560);
            return {
              kind: 'document',
              before,
              after: document.scrollingElement?.scrollTop || 0,
              max: (document.scrollingElement?.scrollHeight || 0) - window.innerHeight
            };
          }
          target.node.scrollBy(0, 560);
          return {
            kind: target.node.tagName,
            before: target.before,
            after: target.node.scrollTop,
            max: target.max
          };
        })()
        """
        return command_id + 1, dict(cls._evaluate(socket, command_id, expression) or {})

    @classmethod
    def _surface(cls, socket, command_id: int) -> tuple[int, dict]:
        expression = r"""
        (() => {
          const visible = node => Boolean(node && node.getClientRects().length);
          const normalize = value => (value || '').replace(/\s+/g, ' ').trim();
          const selector = [
            'input', 'textarea', 'select', '[contenteditable="true"]',
            '[role="textbox"]', '[role="combobox"]', '[role="option"]',
            'button', '[role="button"]'
          ].join(',');
          const controls = [...document.querySelectorAll(selector)]
            .filter(visible)
            .slice(0, 1000)
            .map(node => {
              let context = node;
              for (let depth = 0; depth < 4 && context?.parentElement; depth += 1) {
                if (normalize(context.innerText || context.textContent).length >= 20) break;
                context = context.parentElement;
              }
              return {
                tag: node.tagName,
                type: node.getAttribute('type') || '',
                role: node.getAttribute('role') || '',
                text: normalize(node.innerText || node.textContent).slice(0, 300),
                placeholder: node.getAttribute('placeholder') || '',
                aria_label: node.getAttribute('aria-label') || '',
                contenteditable: node.getAttribute('contenteditable') || '',
                value: 'value' in node ? String(node.value || '').slice(0, 300) : '',
                context: normalize(context?.innerText || context?.textContent).slice(0, 500),
                disabled: Boolean(node.disabled || node.getAttribute('aria-disabled') === 'true')
              };
            });
          return {
            url: location.href,
            title: document.title,
            body_text: (document.body?.innerText || '').slice(0, 120000),
            controls
          };
        })()
        """
        return command_id + 1, dict(cls._evaluate(socket, command_id, expression) or {})

    @classmethod
    def _navigate(cls, socket, command_id: int, url: str, marker: str, timeout: int) -> int:
        cls._cdp_command(socket, command_id, "Page.navigate", {"url": url})
        command_id += 1
        deadline = time.time() + timeout
        while time.time() < deadline:
            body = str(
                cls._evaluate(
                    socket,
                    command_id,
                    "document.body ? document.body.innerText.slice(0, 50000) : ''",
                )
                or ""
            )
            command_id += 1
            if marker in body:
                return command_id
            time.sleep(0.75)
        raise RuntimeError(f"Meta UI timeout while waiting for read-only marker: {marker}")

    def run(
        self,
        profile_key: str,
        ad_account_id: str,
        campaign_id: str,
        adset_id: str,
        ad_id: str,
        output_dir: Path,
    ) -> dict:
        browser_config = self.browser_manager.load_config()
        profile_dir = browser_config.profile_root / profile_key
        if not profile_dir.is_dir():
            raise RuntimeError("Persistent Chrome profile does not exist on worker.")
        output_dir.mkdir(parents=True, exist_ok=True)
        session_dir = output_dir / "browser-session"
        session_dir.mkdir(parents=True, exist_ok=True)
        meta_id = ad_account_id.removeprefix("act_")
        urls = {
            "adset": "https://adsmanager.facebook.com/adsmanager/manage/adsets/edit/standalone?"
            + urlencode(
                {
                    "act": meta_id,
                    "selected_campaign_ids": campaign_id,
                    "selected_adset_ids": adset_id,
                    "selected_ad_ids": ad_id,
                }
            ),
            "ad": "https://adsmanager.facebook.com/adsmanager/manage/ads/edit/standalone?"
            + urlencode(
                {
                    "act": meta_id,
                    "selected_campaign_ids": campaign_id,
                    "selected_adset_ids": adset_id,
                    "selected_ad_ids": ad_id,
                }
            ),
        }
        env = _build_browser_env(
            base_env=os.environ.copy(),
            display=":0",
            profile_dir=profile_dir,
            session_dir=session_dir,
            chromium_bin=browser_config.chromium_bin,
        )
        log_file = (output_dir / "chromium.log").open("ab")
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
                urls["adset"],
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        result = {"safety": {"clicked": False, "published": False}, "stages": {}}
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
                for stage, marker in (("adset", "Tên nhóm quảng cáo"), ("ad", "Tên quảng cáo")):
                    command_id = self._navigate(
                        socket,
                        command_id,
                        urls[stage],
                        marker,
                        self.config.execution_timeout_seconds,
                    )
                    time.sleep(8)
                    command_id, surface = self._surface(socket, command_id)
                    screenshot = self._cdp_command(
                        socket,
                        command_id,
                        "Page.captureScreenshot",
                        {"format": "png", "captureBeyondViewport": False},
                    )
                    command_id += 1
                    (output_dir / f"{stage}.json").write_text(
                        json.dumps(surface, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    (output_dir / f"{stage}.png").write_bytes(
                        base64.b64decode(str(screenshot["data"]))
                    )
                    result["stages"][stage] = {
                        "url": surface.get("url"),
                        "control_count": len(surface.get("controls") or []),
                    }
                    scroll_steps = []
                    for index in range(12):
                        command_id, scroll = self._scroll_editor_down(socket, command_id)
                        if scroll.get("after") == scroll.get("before"):
                            break
                        time.sleep(0.4)
                        command_id, scrolled_surface = self._surface(socket, command_id)
                        (output_dir / f"{stage}-scroll-{index + 1:02d}.json").write_text(
                            json.dumps(scrolled_surface, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        scroll_steps.append(scroll)
                    result["stages"][stage]["scroll_steps"] = scroll_steps
        finally:
            _graceful_shutdown_chromium(process.pid, profile_dir)
            log_file.close()
        (output_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--profile-key", required=True)
    parser.add_argument("--ad-account-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--adset-id", required=True)
    parser.add_argument("--ad-id", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit("Invalid read-only inspection confirmation.")
    config = WorkerConfig.from_env()
    result = DraftFieldInspector(config).run(
        args.profile_key,
        args.ad_account_id,
        args.campaign_id,
        args.adset_id,
        args.ad_id,
        Path(args.output_dir),
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
