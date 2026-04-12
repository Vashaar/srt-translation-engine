from __future__ import annotations

import json
import os
from urllib import error, request

from translator.models import TranslationRequest, TranslationResult
from translator.providers.base import TranslationProvider


class OllamaTranslationProvider(TranslationProvider):
    """Local provider backed by an Ollama server running on localhost."""

    def __init__(self, model: str, base_url: str | None = None) -> None:
        configured = base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
        self.base_url = configured.rstrip("/")
        self.model = model

    def translate(self, request_payload: TranslationRequest) -> TranslationResult:
        system_prompt = (
            "You are an expert subtitle translator for religious, historical, and nuanced lectures. "
            "Preserve meaning, rhetoric, theological precision, and argument structure. "
            "Be conservative with religious names and terms: if uncertain, preserve or transliterate rather than inventing. "
            "Use the aligned script excerpt as the primary source of truth when it clearly corrects subtitle transcription mistakes. "
            "Return strict JSON with keys translated_text, confidence, notes."
        )
        glossary_text = "\n".join(
            f"- {source} => {target}"
            for source, target in request_payload.glossary_terms.items()
        )
        prompt = f"""
Source language: {request_payload.source_language}
Target language: {request_payload.target_language}
Style profile: {request_payload.style_profile}
RTL language: {request_payload.rtl}
Do not translate: {", ".join(request_payload.do_not_translate) or "None"}
Protected terms: {", ".join(request_payload.protected_terms) or "None"}
Glossary rules:
{glossary_text or "- None"}

Subtitle text:
{request_payload.source_subtitle_text}

Aligned script excerpt:
{request_payload.script_context}

Instructions:
- Translate this subtitle block for native-speaker readability.
- Prefer the script excerpt where it clearly fixes transcription errors.
- Keep protected names and sacred terms conservative and consistent.
- If uncertainty remains, mention it in notes.
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

        text = str(raw.get("response", "")).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {
                "translated_text": text,
                "confidence": 0.4,
                "notes": ["Ollama response was not strict JSON; flagged for review."],
            }
        notes = parsed.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        return TranslationResult(
            translated_text=str(parsed.get("translated_text", "")).strip(),
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.4)))),
            notes=[str(item) for item in notes],
            provider_metadata={"provider": "ollama", "model": self.model, "base_url": self.base_url},
        )
