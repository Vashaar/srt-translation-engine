from __future__ import annotations

import json
import os

from openai import OpenAI

from translator.models import TranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class OpenAITranslationProvider(TranslationProvider):
    def __init__(self, model: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def translate(self, request: TranslationRequest) -> TranslationResult:
        system_prompt = (
            "You are an expert subtitle translator for religious, historical, and nuanced lectures. "
            "Preserve meaning, rhetoric, theological precision, tone, and natural phrasing. "
            "Be conservative with religious names and terms: if uncertain, preserve or transliterate rather than inventing. "
            "Use the script excerpt as the primary source of truth when it clearly resolves subtitle transcription issues. "
            "Return valid JSON with keys translated_text, confidence, notes."
        )
        glossary_text = "\n".join(
            f"- {source} => {target}" for source, target in request.glossary_terms.items()
        )
        user_prompt = f"""
Source language: {request.source_language}
Target language: {request.target_language}
Style profile: {request.style_profile}
RTL language: {request.rtl}
Do not translate: {", ".join(request.do_not_translate) or "None"}
Protected terms: {", ".join(request.protected_terms) or "None"}
Glossary rules:
{glossary_text or "- None"}

Subtitle text:
{request.source_subtitle_text}

Aligned script excerpt:
{request.script_context}

Instructions:
- Produce subtitle-ready text only for this block.
- Prefer the script excerpt over likely transcription errors in the subtitle.
- Keep names and technical terms accurate.
- Treat sacred or contested terms conservatively.
- Sound natural for native speakers, not machine-literal.
- Add a short note if anything is uncertain.
"""
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        text = response.output_text
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {
                "translated_text": text.strip(),
                "confidence": 0.5,
                "notes": ["Provider response was not JSON; fallback parser used."],
            }
        translated_text = str(payload.get("translated_text", "")).strip()
        confidence = float(payload.get("confidence", 0.5))
        notes = payload.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        return TranslationResult(
            translated_text=translated_text,
            confidence=max(0.0, min(1.0, confidence)),
            notes=[str(note) for note in notes],
            provider_metadata={"provider": "openai", "model": self.model},
        )
