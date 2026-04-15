from __future__ import annotations

import json


def parse_batch_translation_payload(raw_text: str, expected_indices: list[int]) -> list[str]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("Provider response was not valid JSON.") from exc

    translations = payload.get("translations")
    if not isinstance(translations, list):
        raise ValueError("Provider response must include a 'translations' list.")
    if len(translations) != len(expected_indices):
        raise ValueError("Provider response count did not match the requested batch size.")

    expected_order = [int(index) for index in expected_indices]
    parsed_texts: list[str] = []
    for position, item in enumerate(translations):
        if not isinstance(item, dict):
            raise ValueError("Each translation entry must be an object.")
        index = item.get("index")
        text = item.get("text")
        if index != expected_order[position]:
            raise ValueError("Provider response indices did not match the requested order.")
        if not isinstance(text, str):
            raise ValueError("Each translation entry must include a string 'text' value.")
        parsed_texts.append(text.strip())
    return parsed_texts
