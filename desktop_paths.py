from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from translator.dictionary_store import app_storage_dir


def default_documents_dir() -> Path:
    home = Path.home()
    candidates = [
        home / "Documents",
        home / "OneDrive" / "Documents",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return home / "Documents"


@dataclass(slots=True)
class AppPaths:
    runtime_dir: Path
    bundle_dir: Path
    storage_root: Path
    output_root: Path

    @classmethod
    def detect(cls) -> "AppPaths":
        runtime_dir = cls._detect_runtime_dir()
        bundle_dir = Path(getattr(sys, "_MEIPASS", runtime_dir))
        storage_root = app_storage_dir()
        output_root = default_documents_dir() / "SRTranslate"
        output_root.mkdir(parents=True, exist_ok=True)
        return cls(
            runtime_dir=runtime_dir,
            bundle_dir=bundle_dir,
            storage_root=storage_root,
            output_root=output_root,
        )

    @staticmethod
    def _detect_runtime_dir() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    def resource(self, *parts: str) -> Path:
        bundle_candidate = self.bundle_dir.joinpath(*parts)
        if bundle_candidate.exists():
            return bundle_candidate
        return self.runtime_dir.joinpath(*parts)

    @property
    def config_path(self) -> Path:
        return self.resource("config.yaml")

    @property
    def logo_path(self) -> Path:
        return self.resource("assets", "app_logo.png")

    @property
    def icon_path(self) -> Path:
        return self.resource("assets", "app_icon.ico")

    @property
    def bundled_glossaries_dir(self) -> Path:
        return self.resource("glossaries")

    @property
    def logs_dir(self) -> Path:
        target = self.storage_root / "logs"
        target.mkdir(parents=True, exist_ok=True)
        return target

    @property
    def log_path(self) -> Path:
        return self.logs_dir / "srtranslate.log"
