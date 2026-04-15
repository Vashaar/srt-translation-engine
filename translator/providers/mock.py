from __future__ import annotations

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class MockTranslationProvider(TranslationProvider):
    """Deterministic provider for tests and dry runs."""

    def translate_batch(self, request: BatchTranslationRequest) -> list[TranslationResult]:
        results: list[TranslationResult] = []
        for item in request.items:
            translated = f"[{request.target_language}] {item.script_context or item.source_subtitle_text}"
            results.append(
                TranslationResult(
                    translated_text=translated,
                    confidence=0.55,
                    notes=["Mock translation provider used; output is not production quality."],
                    provider_metadata={"provider": "mock", "batch_size": len(request.items)},
                )
            )
        return results
