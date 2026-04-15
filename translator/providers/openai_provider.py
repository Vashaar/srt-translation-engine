from __future__ import annotations

import json
import os

from openai import OpenAI

from translator.models import BatchTranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider
from translator.providers.structured import parse_batch_translation_payload


class OpenAITranslationProvider(TranslationProvider):
    def __init__(self, model: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def translate_batch(self, request: BatchTranslationRequest) -> list[TranslationResult]:
        system_prompt = (
            "You are an expert subtitle translator for religious, historical, and nuanced lectures. "
            "Preserve meaning, rhetoric, theological precision, tone, and natural phrasing. "
            "Be conservative with religious names and terms: if uncertain, preserve or transliterate rather than inventing. "
            "Use the script excerpt as the primary source of truth when it clearly resolves subtitle transcription issues. "
            "Return strict JSON only in this shape: "
            '{"translations":[{"index":123,"text":"translated subtitle"}]}. '
            "Do not add commentary or extra keys."
        )
        glossary_text = "\n".join(
            f"- {source} => {target}" for source, target in request.glossary_terms.items()
        )
        batch_payload = [
            {
                "index": item.index,
                "previous_subtitle_text": item.previous_subtitle_text,
                "subtitle_text": item.source_subtitle_text,
                "next_subtitle_text": item.next_subtitle_text,
                "aligned_script_excerpt": item.script_context,
            }
            for item in request.items
        ]
        user_prompt = f"""
Source language: {request.source_language}
Target language: {request.target_language}
Style profile: {request.style_profile}
RTL language: {request.rtl}
Do not translate: {", ".join(request.do_not_translate) or "None"}
Protected terms: {", ".join(request.protected_terms) or "None"}
Glossary rules:
{glossary_text or "- None"}

Instructions:
- Translate every subtitle block in order.
- Preserve one translation per requested index.
- Prefer the script excerpt over likely transcription errors in the subtitle.
- Keep names and technical terms accurate.
- Treat sacred or contested terms conservatively.
- Sound natural for native speakers, not machine-literal.
- Never merge, split, or reorder entries.

Batch:
{json.dumps(batch_payload, ensure_ascii=False, indent=2)}
"""
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        texts = parse_batch_translation_payload(
            response.output_text,
            expected_indices=[item.index for item in request.items],
        )
        return [
            TranslationResult(
                translated_text=text,
                confidence=0.75,
                notes=[],
                provider_metadata={
                    "provider": "openai",
                    "model": self.model,
                    "batch_size": len(request.items),
                },
            )
            for text in texts
        ]
