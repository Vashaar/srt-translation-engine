from __future__ import annotations

from pathlib import Path

from translator.models import ScriptDocument
from translator.text import normalize_text, split_script_segments


def parse_script(path: str | Path) -> ScriptDocument:
    script_path = Path(path)
    suffix = script_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        raw_text = script_path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PDF script support requires the 'pypdf' package. Install dependencies or use a .txt/.md script."
            ) from exc
        reader = PdfReader(str(script_path))
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError(f"Unsupported script format: {suffix}")

    normalized = normalize_text(raw_text)
    segments = split_script_segments(raw_text)
    return ScriptDocument(
        path=script_path,
        raw_text=raw_text,
        normalized_text=normalized,
        segments=segments,
    )
