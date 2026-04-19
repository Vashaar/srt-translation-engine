from __future__ import annotations

import re
import textwrap
import unicodedata


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed


def clean_translated_text(
    text: str,
    *,
    source_text: str = "",
    language: str = "",
    normalize_grammar_enabled: bool = True,
) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("\ufeff", "").replace("\ufffd", " ")
    cleaned = _strip_control_characters(cleaned)
    cleaned = _remove_duplicate_lines(cleaned)
    cleaned = _remove_repeated_phrases(cleaned)
    cleaned = _remove_repeated_words(cleaned)
    cleaned = _normalize_spacing(cleaned, language)
    if normalize_grammar_enabled:
        cleaned = _normalize_sentence_grammar(cleaned, language)
    cleaned = normalize_text(cleaned)
    return cleaned or normalize_text(source_text)


def split_script_segments(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [normalize_text(chunk) for chunk in chunks if normalize_text(chunk)]


def rebalance_subtitle_lines(
    text: str,
    max_chars_per_line: int,
    max_lines: int = 2,
) -> list[str]:
    flattened = normalize_text(" ".join(segment.strip() for segment in text.splitlines() if segment.strip()))
    if not flattened:
        return [""]
    if max_lines <= 1:
        shortened = shorten_subtitle_text(flattened, max_chars_per_line)
        return [shortened]
    if len(flattened) <= max_chars_per_line:
        return [flattened]

    candidate_text = shorten_subtitle_text(flattened, max_chars_per_line * max_lines)
    lines = _split_balanced_lines(candidate_text, max_chars_per_line, max_lines)
    if len(lines) > max_lines:
        candidate_text = shorten_subtitle_text(candidate_text, max_chars_per_line * max_lines)
        lines = _split_balanced_lines(candidate_text, max_chars_per_line, max_lines)
    return lines[:max_lines] or [candidate_text]


def shorten_subtitle_text(text: str, max_total_chars: int) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= max_total_chars:
        return normalized

    shortened = re.sub(r"\([^)]*\)", "", normalized)
    shortened = normalize_text(shortened)
    if len(shortened) <= max_total_chars:
        return shortened

    fillers = [
        r"\byou know\b",
        r"\bi mean\b",
        r"\bwell\b",
        r"\bjust\b",
        r"\bperhaps\b",
        r"\bquite\b",
    ]
    for filler in fillers:
        shortened = re.sub(filler, "", shortened, flags=re.IGNORECASE)
        shortened = normalize_text(shortened)
        if len(shortened) <= max_total_chars:
            return shortened

    clauses = re.split(r"(?<=[,;:])\s+", shortened)
    if len(clauses) > 1:
        kept: list[str] = []
        total_length = 0
        for clause in clauses:
            proposed_length = total_length + len(clause) + (2 if kept else 0)
            if proposed_length > max_total_chars:
                break
            kept.append(clause)
            total_length = proposed_length
        if kept:
            shortened = normalize_text(", ".join(kept))
            if len(shortened) <= max_total_chars:
                return shortened

    return textwrap.shorten(shortened, width=max_total_chars, placeholder="...")


def _split_balanced_lines(text: str, max_chars_per_line: int, max_lines: int) -> list[str]:
    if max_lines != 2:
        wrapped = textwrap.wrap(
            text,
            width=max_chars_per_line,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return wrapped[:max_lines] or [text]
    if len(text) <= max_chars_per_line:
        return [text]

    best_pair: tuple[int, str, str] | None = None
    for match in re.finditer(r"\s+", text):
        split_at = match.start()
        left = text[:split_at].strip()
        right = text[match.end():].strip()
        if not left or not right:
            continue
        score = _line_split_score(left, right, text, split_at, max_chars_per_line)
        if best_pair is None or score < best_pair[0]:
            best_pair = (score, left, right)

    if best_pair is None:
        return textwrap.wrap(
            text,
            width=max_chars_per_line,
            break_long_words=False,
            break_on_hyphens=False,
        )[:max_lines] or [text]

    _, left, right = best_pair
    return [left, right]


def _line_split_score(left: str, right: str, source: str, split_at: int, max_chars_per_line: int) -> int:
    overflow_penalty = max(0, len(left) - max_chars_per_line) + max(0, len(right) - max_chars_per_line)
    balance_penalty = abs(len(left) - len(right))
    short_line_penalty = 50 if len(left.split()) < 2 or len(right.split()) < 2 else 0
    punctuation_bonus = -15 if source[max(0, split_at - 1)] in {",", ";", ":"} else 0
    conjunction_bonus = -10 if re.search(r"\b(and|but|or|because|that|which|while|when)\b$", left, re.IGNORECASE) else 0
    return overflow_penalty * 20 + balance_penalty + short_line_penalty + punctuation_bonus + conjunction_bonus


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


def _strip_control_characters(text: str) -> str:
    allowed = []
    for char in text:
        if char in {"\n", "\t"}:
            allowed.append(char)
            continue
        if unicodedata.category(char).startswith("C"):
            continue
        allowed.append(char)
    return "".join(allowed)


def _remove_duplicate_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    previous = ""
    for line in text.splitlines():
        normalized = normalize_text(line)
        if not normalized:
            continue
        if normalized.casefold() == previous.casefold():
            continue
        cleaned_lines.append(normalized)
        previous = normalized
    return "\n".join(cleaned_lines)


def _remove_repeated_phrases(text: str) -> str:
    segments = re.split(r"(?<=[.!?؟])\s+", normalize_text(text))
    deduped: list[str] = []
    previous = ""
    for segment in segments:
        normalized = normalize_text(segment)
        if not normalized:
            continue
        if normalized.casefold() == previous.casefold():
            continue
        deduped.append(normalized)
        previous = normalized
    return " ".join(deduped)


def _remove_repeated_words(text: str) -> str:
    collapsed = re.sub(r"\b(\w+)(?:\s+\1){2,}\b", r"\1", text, flags=re.IGNORECASE)
    collapsed = re.sub(r"([!?.,;:])\1{1,}", r"\1", collapsed)
    return collapsed


def _normalize_spacing(text: str, language: str) -> str:
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", text)
    cleaned = re.sub(r"([,.;:!?])(?!\s|$)", r"\1 ", cleaned)
    if language in {"ar", "fa", "ur"}:
        cleaned = re.sub(r"\s+([،؛؟])", r"\1", cleaned)
        cleaned = re.sub(r"([،؛؟])(?!\s|$)", r"\1 ", cleaned)
    return cleaned


def _normalize_sentence_grammar(text: str, language: str) -> str:
    if language in {"ar", "fa", "ur"}:
        return text
    normalized = text
    should_capitalize_first = bool(
        normalized
        and normalized[0].isalpha()
        and (re.search(r"\s", normalized) or normalized.endswith((".", "!", "?")))
    )
    if should_capitalize_first:
        normalized = normalized[0].upper() + normalized[1:]

    def _capitalize(match: re.Match[str]) -> str:
        prefix = match.group(1)
        letter = match.group(2)
        return f"{prefix}{letter.upper()}"

    return re.sub(r"([.!?]\s+)([a-z])", _capitalize, normalized)
