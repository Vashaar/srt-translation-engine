from __future__ import annotations

from translator.providers.base import TranslationProvider
from translator.providers.manual_provider import ManualTranslationProvider
from translator.providers.mock import MockTranslationProvider


def build_provider(provider_name: str, model: str) -> TranslationProvider:
    if provider_name == "mock":
        return MockTranslationProvider()
    if provider_name == "manual":
        return ManualTranslationProvider()
    if provider_name == "ollama":
        from translator.providers.ollama_provider import OllamaTranslationProvider

        return OllamaTranslationProvider(model=model)
    if provider_name == "openai":
        from translator.providers.openai_provider import OpenAITranslationProvider

        return OpenAITranslationProvider(model=model)
    raise ValueError(f"Unsupported provider: {provider_name}")
