from __future__ import annotations

import re
import textwrap


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed


def split_script_segments(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [normalize_text(chunk) for chunk in chunks if normalize_text(chunk)]


def rebalance_subtitle_lines(text: str, max_chars_per_line: int) -> list[str]:
    paragraphs = [segment.strip() for segment in text.splitlines() if segment.strip()]
    if not paragraphs:
        return [""]
    lines: list[str] = []
    for paragraph in paragraphs:
        wrapped = textwrap.wrap(
            paragraph,
            width=max_chars_per_line,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [""])
    return lines


def contains_substantial_source_text(
    translated_text: str,
    source_text: str,
    allowed_tokens: list[str],
) -> bool:
    source_words = {
        token.lower()
        for token in re.findall(r"[A-Za-z']+", source_text)
        if token.lower() not in {item.lower() for item in allowed_tokens}
    }
    translated_words = {token.lower() for token in re.findall(r"[A-Za-z']+", translated_text)}
    overlap = source_words & translated_words
    return bool(source_words) and len(overlap) / max(len(source_words), 1) > 0.45


def is_rtl_language(lang: str) -> bool:
    return lang in {"ur", "ar", "fa", "he"}
