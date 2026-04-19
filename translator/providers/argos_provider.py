from __future__ import annotations

import json
import logging
import re
import threading
import time
from urllib import request

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider

logger = logging.getLogger(__name__)

_PACKAGE_LOCK = threading.Lock()
_SUSPICIOUS_PREFIX_RE = re.compile(
    r"^\s*(refined translation|translation|output|subtitle)\s*:",
    flags=re.IGNORECASE,
)


def _import_argos_modules():
    try:
        from argostranslate import package as argos_package
        from argostranslate import translate as argos_translate
    except ImportError as exc:
        raise RuntimeError(
            "Argos Translate is not installed. Install dependencies from requirements.txt."
        ) from exc
    return argos_package, argos_translate


def _find_installed_translation(source_code: str, target_code: str):
    _, argos_translate = _import_argos_modules()
    from_language = argos_translate.get_language_from_code(source_code)
    to_language = argos_translate.get_language_from_code(target_code)
    if from_language is None or to_language is None:
        return None
    return from_language.get_translation(to_language)


def _package_matches(package_obj, source_code: str, target_code: str) -> bool:
    if getattr(package_obj, "type", "translate") != "translate":
        return False
    package_from_codes = getattr(package_obj, "from_codes", None) or []
    package_to_codes = getattr(package_obj, "to_codes", None) or []
    from_codes = {
        str(code).lower()
        for code in [
            getattr(package_obj, "from_code", None),
            *package_from_codes,
        ]
        if code
    }
    to_codes = {
        str(code).lower()
        for code in [
            getattr(package_obj, "to_code", None),
            *package_to_codes,
        ]
        if code
    }
    return source_code.lower() in from_codes and target_code.lower() in to_codes


def _ensure_argos_translation(source_code: str, target_code: str, *, auto_download: bool):
    installed = _find_installed_translation(source_code, target_code)
    if installed is not None:
        return installed

    if not auto_download:
        raise RuntimeError(
            f"Argos language pack {source_code}->{target_code} is not installed."
        )

    argos_package, argos_translate = _import_argos_modules()
    with _PACKAGE_LOCK:
        installed = _find_installed_translation(source_code, target_code)
        if installed is not None:
            return installed

        logger.info("Downloading Argos language pack %s->%s", source_code, target_code)
        argos_package.update_package_index()
        available_packages = argos_package.get_available_packages()
        package_obj = next(
            (
                candidate
                for candidate in available_packages
                if _package_matches(candidate, source_code, target_code)
            ),
            None,
        )
        if package_obj is None:
            raise RuntimeError(
                f"Argos does not list a language pack for {source_code}->{target_code}."
            )
        package_obj.install()
        argos_translate.load_installed_languages()

    installed = _find_installed_translation(source_code, target_code)
    if installed is None:
        raise RuntimeError(
            f"Argos language pack {source_code}->{target_code} was installed but could not be loaded."
        )
    return installed


def ensure_argos_language_pair(source_code: str, target_code: str, *, auto_download: bool = True) -> None:
    _ensure_argos_translation(source_code, target_code, auto_download=auto_download)


def _extract_chat_content(raw: dict[str, object]) -> str:
    try:
        return str(raw["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LM Studio returned an unexpected response payload.") from exc


def _strip_plain_text_response(text: str) -> str:
    cleaned = str(text or "").strip()
    fenced = re.fullmatch(r"```(?:text)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced is not None:
        cleaned = fenced.group(1).strip()
    cleaned = _SUSPICIOUS_PREFIX_RE.sub("", cleaned, count=1).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _looks_suspicious_refinement(refined: str, rough_translation: str) -> bool:
    refined_text = str(refined or "").strip()
    if not refined_text:
        return True
    lowered = refined_text.lower()
    if any(marker in lowered for marker in ("original english", "argos rough", "instructions:", "{", "}")):
        return True
    rough_length = max(1, len(str(rough_translation or "").strip()))
    return rough_length > 8 and len(refined_text) > rough_length * 3


def _fallback_result(
    *,
    text: str,
    confidence: float,
    note: str,
    metadata: dict[str, object],
) -> TranslationResult:
    return TranslationResult(
        translated_text=text,
        confidence=confidence,
        notes=[note],
        provider_metadata=metadata,
    )


class ArgosTranslationProvider(TranslationProvider):
    """Two-pass local provider: Argos draft, LM Studio refinement."""

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        auto_download: bool = True,
        refine_with_lmstudio: bool = True,
    ) -> None:
        configured = base_url or "http://127.0.0.1:1234/v1"
        self.base_url = configured.rstrip("/")
        self.model = model
        self.auto_download = bool(auto_download)
        self.refine_with_lmstudio = bool(refine_with_lmstudio)
        self.device = "CPU (Argos) + GPU (LM Studio)" if self.refine_with_lmstudio else "CPU (Argos)"
        self.precision = "mixed" if self.refine_with_lmstudio else "offline"

    def translate_batch(self, request_payload: BatchTranslationRequest) -> list[TranslationResult]:
        source_code = request_payload.source_language or "en"
        target_code = request_payload.target_language
        target_language = request_payload.target_language_name or target_code
        translation = _ensure_argos_translation(
            source_code,
            target_code,
            auto_download=self.auto_download,
        )

        results: list[TranslationResult] = []
        for item in request_payload.items:
            rough_translation = str(translation.translate(item.source_subtitle_text) or "").strip()
            base_metadata = {
                "provider": "argos",
                "first_pass_provider": "argos",
                "refinement_provider": "lmstudio",
                "model": self.model,
                "base_url": self.base_url,
                "source_language": source_code,
                "target_language": target_code,
                "device": self.device,
                "precision": self.precision,
            }
            if not rough_translation:
                logger.warning("Argos returned an empty draft for block %s.", item.index)
                results.append(
                    _fallback_result(
                        text="...",
                        confidence=0.0,
                        note=(
                            "Argos returned an empty first-pass translation; placeholder text was used."
                        ),
                        metadata={
                            **base_metadata,
                            "provider": "fallback",
                            "upstream_provider": "argos",
                            "first_pass_empty": True,
                        },
                    )
                )
                continue
            if not self.refine_with_lmstudio:
                results.append(
                    TranslationResult(
                        translated_text=rough_translation,
                        confidence=0.62,
                        notes=[],
                        provider_metadata={
                            **base_metadata,
                            "refinement_skipped": True,
                        },
                    )
                )
                continue
            started_at = time.perf_counter()
            try:
                refined_text = self._refine_translation(
                    previous_text=item.previous_subtitle_text,
                    source_text=item.source_subtitle_text,
                    next_text=item.next_subtitle_text,
                    rough_translation=rough_translation,
                    target_language=target_language,
                    request_payload=request_payload,
                )
                if _looks_suspicious_refinement(refined_text, rough_translation):
                    raise RuntimeError("LM Studio refinement looked non-subtitle-like.")
                latency = time.perf_counter() - started_at
                results.append(
                    TranslationResult(
                        translated_text=refined_text,
                        confidence=0.78,
                        notes=[],
                        provider_metadata={
                            **base_metadata,
                            "latency_seconds": latency,
                        },
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Argos second-pass refinement failed for block %s; using Argos draft: %s",
                    item.index,
                    exc,
                )
                results.append(
                    _fallback_result(
                        text=rough_translation,
                        confidence=0.52,
                        note="LM Studio refinement failed; Argos first-pass translation was used.",
                        provider_metadata={
                            **base_metadata,
                            "refinement_failed": True,
                            "error": str(exc),
                        },
                    )
                )
        return results

    def _refine_translation(
        self,
        *,
        previous_text: str,
        source_text: str,
        next_text: str,
        rough_translation: str,
        target_language: str,
        request_payload: BatchTranslationRequest,
    ) -> str:
        prompt = self._build_refinement_prompt(
            previous_text=previous_text,
            source_text=source_text,
            next_text=next_text,
            rough_translation=rough_translation,
            target_language=target_language,
            request_payload=request_payload,
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You refine subtitle translations. Return only the refined subtitle text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
        refined = _strip_plain_text_response(_extract_chat_content(raw))
        if not refined:
            raise RuntimeError("LM Studio returned an empty refinement.")
        return refined

    @staticmethod
    def _build_refinement_prompt(
        *,
        previous_text: str,
        source_text: str,
        next_text: str,
        rough_translation: str,
        target_language: str,
        request_payload: BatchTranslationRequest,
    ) -> str:
        protected_terms = ", ".join(
            term
            for term in [
                *request_payload.do_not_translate,
                *request_payload.protected_terms,
                "Allah",
                "Qur'an",
                "Quran",
                "Hadith",
                "Sunnah",
                "Prophet",
                "Messenger",
                "Rasulullah",
                "Subhanahu wa ta'ala",
                "alayhi as-salam",
                "peace be upon him",
                "sallallahu alayhi wa sallam",
                "Jannah",
                "Jahannam",
                "Salah",
                "Zakah",
                "Tawhid",
            ]
            if str(term).strip()
        )
        glossary_text = "\n".join(
            f"- {source}: {target}"
            for source, target in request_payload.glossary_terms.items()
        )
        return f"""Refine this rough subtitle translation into {target_language}.

Previous English subtitle for context only:
{previous_text or "[none]"}

Original English subtitle:
{source_text}

Next English subtitle for context only:
{next_text or "[none]"}

Argos rough translation:
{rough_translation}

Instructions:
- Refine only the current subtitle, not the previous or next context.
- Preserve the meaning of the English line exactly.
- Do not add explanation, interpretation, or religious commentary.
- Keep the refined text close in length to the Argos draft unless grammar requires a small change.
- Preserve all Islamic terminology and honorifics unchanged.
- Preserve these protected terms unchanged: {protected_terms or "None"}.
- Do not translate protected Islamic terms or honorifics if they are already preserved in the draft.
- Do not replace religious terms with approximate secular equivalents.
- Do not remove diacritics or alter protected glossary spellings.
- Keep the subtitle concise and natural.
- Do not add commentary, explanations, quotes, labels, or JSON.
- Return only the refined subtitle text.

Glossary:
{glossary_text or "- None"}
"""
