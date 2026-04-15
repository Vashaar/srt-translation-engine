from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher

from translator.models import TranslationResult
from translator.text import normalize_text


class TranslationMemory:
    def __init__(self) -> None:
        self._exact: dict[str, TranslationResult] = {}

    def lookup(self, source_text: str) -> TranslationResult | None:
        normalized = normalize_text(source_text)
        if normalized in self._exact:
            return self._clone(self._exact[normalized], "Translation memory exact match reused.")

        best_key = ""
        best_score = 0.0
        for candidate in self._exact:
            score = SequenceMatcher(None, normalized.lower(), candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_key = candidate
        if best_key and best_score >= 0.94:
            return self._clone(
                self._exact[best_key],
                f"Translation memory fuzzy match reused ({best_score:.2f}).",
            )
        return None

    def remember(self, source_text: str, result: TranslationResult) -> None:
        normalized = normalize_text(source_text)
        self._exact[normalized] = replace(
            result,
            notes=list(result.notes),
            provider_metadata=dict(result.provider_metadata),
        )

    @staticmethod
    def _clone(result: TranslationResult, note: str) -> TranslationResult:
        cloned_notes = list(result.notes)
        cloned_notes.append(note)
        return replace(
            result,
            notes=cloned_notes,
            provider_metadata=dict(result.provider_metadata),
        )
