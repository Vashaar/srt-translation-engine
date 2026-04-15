from __future__ import annotations

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class ManualTranslationProvider(TranslationProvider):
    """Local/manual stub that marks every segment for human translation."""

    def translate_batch(self, request: BatchTranslationRequest) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for item in request.items:
            notes = [
                "Manual provider stub used.",
                "No automatic translation was performed.",
                "Human review and translation are required.",
            ]
            results.append(
                TranslationResult(
                    translated_text=item.source_subtitle_text,
                    confidence=0.0,
                    notes=notes,
                    provider_metadata={"provider": "manual", "batch_size": len(request.items)},
                )
            )
        return results
