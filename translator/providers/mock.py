from __future__ import annotations

from translator.models import TranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class MockTranslationProvider(TranslationProvider):
    """Deterministic provider for tests and dry runs."""

    def translate(self, request: TranslationRequest) -> TranslationResult:
        translated = f"[{request.target_language}] {request.script_context or request.source_subtitle_text}"
        return TranslationResult(
            translated_text=translated,
            confidence=0.55,
            notes=["Mock translation provider used; output is not production quality."],
            provider_metadata={"provider": "mock"},
        )
