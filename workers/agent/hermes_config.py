from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml


class HermesConfigManager:
    def __init__(self, hermes_home: Path):
        self.home = hermes_home
        self.config_path = hermes_home / "config.yaml"
        self.managed_hash_path = hermes_home / ".ads-lush-provider.sha256"

    def apply(self, provider: dict | None) -> bool:
        if not provider:
            return False
        canonical = json.dumps(provider, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        if self.managed_hash_path.exists() and self.managed_hash_path.read_text(
            encoding="utf-8"
        ).strip() == digest:
            return False

        self.home.mkdir(parents=True, exist_ok=True)
        config: dict = {}
        if self.config_path.exists():
            loaded = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = loaded
        model = config.get("model")
        if not isinstance(model, dict):
            model = {}
            config["model"] = model
        model.update(
            {
                "provider": "custom",
                "default": str(provider["model"]),
                "base_url": str(provider["base_url"]),
                "api_key": str(provider.get("api_key") or ""),
            }
        )
        temporary = self.config_path.with_suffix(".yaml.tmp")
        temporary.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.config_path)
        self.managed_hash_path.write_text(digest, encoding="utf-8")
        os.chmod(self.managed_hash_path, 0o600)
        subprocess.run(
            ["systemctl", "enable", "--now", "meta-ads-copilot-hermes.service"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
