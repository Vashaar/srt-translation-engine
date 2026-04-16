from __future__ import annotations

import json
import re
from dataclasses import dataclass


TRANSLATION_JSON_CONTRACT = (
    'Return valid JSON only in this exact shape: '
    '{"translations":[{"index":123,"text":"translated subtitle"}]}. '
    "The translations array must contain exactly one object per requested subtitle, "
    "in the same order as requested, with integer index values and string text values."
)


@dataclass(slots=True)
class ParsedBatchTranslations:
    texts: list[str]
    missing_indices: list[int]
    extra_indices: list[int]
    duplicate_indices: list[int]
    invalid_entries: int
    reordered: bool

    @property
    def strict_match(self) -> bool:
        return not (
            self.missing_indices
            or self.extra_indices
            or self.duplicate_indices
            or self.invalid_entries
            or self.reordered
        )

    def metadata(self) -> dict[str, object]:
        return {
            "strict_match": self.strict_match,
            "missing_indices": list(self.missing_indices),
            "extra_indices": list(self.extra_indices),
            "duplicate_indices": list(self.duplicate_indices),
            "invalid_entries": self.invalid_entries,
            "reordered": self.reordered,
        }


def _extract_json_payload(raw_text: str) -> dict[str, object]:
    candidate = str(raw_text or "").strip()
    if candidate.startswith("```"):
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.DOTALL)
        if fenced is not None:
            candidate = fenced.group(1)
    if not candidate.startswith("{"):
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if match is not None:
            candidate = match.group(0)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("Provider response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Provider response must be a JSON object.")
    return payload


def parse_batch_translation_payload(raw_text: str, expected_indices: list[int]) -> ParsedBatchTranslations:
    payload = _extract_json_payload(raw_text)
    translations = payload.get("translations")
    if not isinstance(translations, list):
        raise ValueError("Provider response must include a 'translations' list.")

    expected_order = [int(index) for index in expected_indices]
    expected_set = set(expected_order)
    resolved_texts: dict[int, str] = {}
    encountered_expected: list[int] = []
    extra_indices: list[int] = []
    duplicate_indices: list[int] = []
    invalid_entries = 0

    for item in translations:
        if not isinstance(item, dict):
            invalid_entries += 1
            continue
        index = item.get("index")
        text = item.get("text")
        if isinstance(index, bool) or not isinstance(index, int):
            invalid_entries += 1
            continue
        if not isinstance(text, str):
            invalid_entries += 1
            continue
        if index not in expected_set:
            extra_indices.append(index)
            continue
        if index in resolved_texts:
            duplicate_indices.append(index)
            continue
        encountered_expected.append(index)
        resolved_texts[index] = text.strip()

    missing_indices = [index for index in expected_order if index not in resolved_texts]
    texts = [resolved_texts.get(index, "") for index in expected_order]
    reordered = encountered_expected != [index for index in expected_order if index in resolved_texts]
    return ParsedBatchTranslations(
        texts=texts,
        missing_indices=missing_indices,
        extra_indices=extra_indices,
        duplicate_indices=duplicate_indices,
        invalid_entries=invalid_entries,
        reordered=reordered,
    )
