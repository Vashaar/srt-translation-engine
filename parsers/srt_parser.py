from __future__ import annotations

import re
from pathlib import Path

from translator.models import SubtitleBlock

TIMESTAMP_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s-->\s(?P<end>\d{2}:\d{2}:\d{2},\d{3})$"
)


def parse_srt(path: str | Path) -> list[SubtitleBlock]:
    srt_path = Path(path)
    content = srt_path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", content.strip())
    parsed: list[SubtitleBlock] = []
    for raw_block in blocks:
        lines = [line.rstrip("\r") for line in raw_block.splitlines()]
        if len(lines) < 3:
            raise ValueError(f"Invalid SRT block: {raw_block}")
        index = int(lines[0].strip())
        match = TIMESTAMP_RE.match(lines[1].strip())
        if not match:
            raise ValueError(f"Invalid timestamp line in block {index}: {lines[1]}")
        text_lines = [line for line in lines[2:] if line.strip() != ""]
        parsed.append(
            SubtitleBlock(
                index=index,
                start=match.group("start"),
                end=match.group("end"),
                lines=text_lines,
            )
        )
    return parsed


def build_srt_blocks(
    source_blocks: list[SubtitleBlock], translated_texts: list[list[str]]
) -> list[SubtitleBlock]:
    return [
        SubtitleBlock(
            index=source.index,
            start=source.start,
            end=source.end,
            lines=lines,
        )
        for source, lines in zip(source_blocks, translated_texts, strict=True)
    ]
