from __future__ import annotations

from translator.models import TranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class ManualTranslationProvider(TranslationProvider):
    """Local/manual stub that marks every segment for human translation."""

    def translate(self, request: TranslationRequest) -> TranslationResult:
        notes = [
            "Manual provider stub used.",
            "No automatic translation was performed.",
            "Human review and translation are required.",
        ]
        return TranslationResult(
            translated_text=request.source_subtitle_text,
            confidence=0.0,
            notes=notes,
            provider_metadata={"provider": "manual"},
        )
