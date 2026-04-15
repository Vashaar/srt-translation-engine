from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AppConfig:
    raw: dict[str, Any]

    @property
    def source_language(self) -> str:
        return str(self.raw.get("source_language", "en"))

    @property
    def provider(self) -> str:
        return str(self.raw.get("provider", "ollama"))

    @property
    def model(self) -> str:
        return str(self.raw.get("model", "qwen2.5:7b-instruct"))

    @property
    def style_profile(self) -> str:
        return str(self.raw.get("style_profile", "balanced"))

    @property
    def output_dir(self) -> Path:
        output = self.raw.get("output", {}).get("output_dir", "outputs")
        return Path(output)

    @property
    def low_confidence_threshold(self) -> float:
        return float(
            self.raw.get("translation", {}).get("low_confidence_threshold", 0.7)
        )

    @property
    def retry_low_confidence(self) -> bool:
        return bool(self.raw.get("translation", {}).get("retry_low_confidence", True))

    @property
    def max_repair_attempts(self) -> int:
        return int(self.raw.get("translation", {}).get("max_repair_attempts", 1))

    @property
    def line_rebalancing_enabled(self) -> bool:
        return bool(
            self.raw.get("line_rebalancing", {}).get("enabled", False)
        )

    @property
    def max_chars_per_line(self) -> int:
        return int(
            self.raw.get("line_rebalancing", {}).get("max_chars_per_line", 42)
        )

    @property
    def max_lines_per_subtitle(self) -> int:
        return int(
            self.raw.get("line_rebalancing", {}).get("max_lines_per_subtitle", 2)
        )

    @property
    def translation_batch_size(self) -> int:
        value = int(self.raw.get("translation", {}).get("batch_size", 10))
        return max(5, min(15, value))

    @property
    def alignment_search_radius(self) -> int:
        value = int(self.raw.get("alignment", {}).get("search_radius", 5))
        return max(1, value)

    def language_settings(self, lang: str) -> dict[str, Any]:
        return dict(self.raw.get("language_settings", {}).get(lang, {}))

    def provider_settings(self, provider_name: str) -> dict[str, Any]:
        return dict(self.raw.get("providers", {}).get(provider_name, {}))


def load_config(path: str | Path | None) -> AppConfig:
    config_path = Path(path or "config.yaml")
    if not config_path.exists():
        return AppConfig(raw={})
    with config_path.open("r", encoding="utf-8") as handle:
        return AppConfig(raw=yaml.safe_load(handle) or {})
