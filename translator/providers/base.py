from __future__ import annotations

from abc import ABC, abstractmethod

from translator.models import TranslationRequest, TranslationResult


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResult:
        raise NotImplementedError
