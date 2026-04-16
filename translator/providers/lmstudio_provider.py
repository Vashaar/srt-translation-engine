from __future__ import annotations

import json
from urllib import error, request

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider
from translator.providers.structured import (
    TRANSLATION_JSON_CONTRACT,
    parse_batch_translation_payload,
)


class LMStudioTranslationProvider(TranslationProvider):
    """OpenAI-compatible local provider backed by LM Studio."""

    def __init__(self, model: str, base_url: str | None = None) -> None:
        configured = base_url or "http://localhost:1234/v1"
        self.base_url = configured.rstrip("/")
        self.model = model
        self.device = "GPU (LM Studio)"
        self.precision = "fp16"

    def translate_batch(self, request_payload: BatchTranslationRequest) -> list[TranslationResult]:
        target_language = request_payload.target_language_name or request_payload.target_language
        glossary_text = "\n".join(
            f"- {source} => {target}"
            for source, target in request_payload.glossary_terms.items()
        )
        batch_payload = [
            {
                "index": item.index,
                "previous_subtitle_text": item.previous_subtitle_text,
                "subtitle_text": item.source_subtitle_text,
                "next_subtitle_text": item.next_subtitle_text,
                "aligned_script_excerpt": item.script_context,
            }
            for item in request_payload.items
        ]
        translation_prompt = f"""
Translate the subtitle batch below.

Source language: {request_payload.source_language}
Target language: {target_language} ({request_payload.target_language})
Style profile: {request_payload.style_profile}
RTL language: {request_payload.rtl}
Do not translate: {", ".join(request_payload.do_not_translate) or "None"}
Protected terms: {", ".join(request_payload.protected_terms) or "None"}
Glossary rules:
{glossary_text or "- None"}

Instructions:
- Translate every subtitle block in order.
- Preserve one translation per requested index.
- Prefer the aligned script excerpt where it clearly resolves subtitle transcription mistakes.
- Keep names and protected terms conservative and consistent.
- Do not merge, split, or reorder entries.
- Return valid JSON only.
- {TRANSLATION_JSON_CONTRACT}

Batch:
{json.dumps(batch_payload, ensure_ascii=False, indent=2)}
"""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise subtitle translator."},
                {"role": "user", "content": translation_prompt},
            ],
            "temperature": 0.2,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=180) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                "Could not reach the local LM Studio server. Start LM Studio or switch providers."
            ) from exc

        try:
            content = str(raw["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LM Studio returned an unexpected response payload.") from exc

        parsed = parse_batch_translation_payload(
            content,
            expected_indices=[item.index for item in request_payload.items],
        )
        shared_metadata = {
            "provider": "lmstudio",
            "model": self.model,
            "base_url": self.base_url,
            "device": self.device,
            "precision": self.precision,
            "batch_size": len(request_payload.items),
            "structured_output": parsed.metadata(),
        }
        results: list[TranslationResult] = []
        for item, text in zip(request_payload.items, parsed.texts, strict=True):
            notes: list[str] = []
            confidence = 0.75
            if item.index in parsed.missing_indices:
                notes.append("Missing translation entry was detected in the batch output.")
                confidence = 0.0
            if item.index in parsed.duplicate_indices:
                notes.append("Duplicate translation entry was detected and repaired by index.")
            results.append(
                TranslationResult(
                    translated_text=text,
                    confidence=confidence,
                    notes=notes,
                    provider_metadata=shared_metadata,
                )
            )
        return results
