from __future__ import annotations

import json
import os
from urllib import error, request

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider
from translator.providers.structured import parse_batch_translation_payload


class OllamaTranslationProvider(TranslationProvider):
    """Local provider backed by an Ollama server running on localhost."""

    def __init__(self, model: str, base_url: str | None = None) -> None:
        configured = base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
        self.base_url = configured.rstrip("/")
        self.model = model

    def translate_batch(self, request_payload: BatchTranslationRequest) -> list[TranslationResult]:
        system_prompt = (
            "You are an expert subtitle translator for religious, historical, and nuanced lectures. "
            "Preserve meaning, rhetoric, theological precision, and argument structure. "
            "Be conservative with religious names and terms: if uncertain, preserve or transliterate rather than inventing. "
            "Use the aligned script excerpt as the primary source of truth when it clearly corrects subtitle transcription mistakes. "
            "Return strict JSON only in this shape: "
            '{"translations":[{"index":123,"text":"translated subtitle"}]}. '
            "Do not add commentary or extra keys."
        )
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
        prompt = f"""
Source language: {request_payload.source_language}
Target language: {request_payload.target_language}
Style profile: {request_payload.style_profile}
RTL language: {request_payload.rtl}
Do not translate: {", ".join(request_payload.do_not_translate) or "None"}
Protected terms: {", ".join(request_payload.protected_terms) or "None"}
Glossary rules:
{glossary_text or "- None"}

Instructions:
- Translate every subtitle block in order.
- Prefer the script excerpt where it clearly fixes transcription errors.
- Keep protected names and sacred terms conservative and consistent.
- Never merge, split, or reorder entries.

Batch:
{json.dumps(batch_payload, ensure_ascii=False, indent=2)}
"""
        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "system": system_prompt,
            "prompt": prompt,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=180) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                "Could not reach the local Ollama server. Start Ollama or switch providers."
            ) from exc

        texts = parse_batch_translation_payload(
            str(raw.get("response", "")).strip(),
            expected_indices=[item.index for item in request_payload.items],
        )
        return [
            TranslationResult(
                translated_text=text,
                confidence=0.65,
                notes=[],
                provider_metadata={
                    "provider": "ollama",
                    "model": self.model,
                    "base_url": self.base_url,
                    "batch_size": len(request_payload.items),
                },
            )
            for text in texts
        ]
