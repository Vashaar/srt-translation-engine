from __future__ import annotations

from pathlib import Path

import yaml


def load_glossary(path: str | Path | None) -> dict[str, object]:
    if not path:
        return {"terms": {}, "do_not_translate": [], "protected_terms": []}
    glossary_path = Path(path)
    if not glossary_path.exists():
        raise FileNotFoundError(f"Glossary file not found: {glossary_path}")
    with glossary_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return {
        "terms": dict(data.get("terms", {})),
        "do_not_translate": list(data.get("do_not_translate", [])),
        "protected_terms": list(data.get("protected_terms", [])),
    }
