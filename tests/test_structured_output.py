from translator.config import AppConfig
from translator.providers.structured import parse_batch_translation_payload
from translator.text import clean_translated_text


def test_structured_output_parser_repairs_alignment_gaps() -> None:
    parsed = parse_batch_translation_payload(
        """
        {
          "translations": [
            {"index": 2, "text": "dos"},
            {"index": 99, "text": "extra"},
            {"index": 2, "text": "duplicate"}
          ]
        }
        """,
        expected_indices=[1, 2, 3],
    )

    assert parsed.texts == ["", "dos", ""]
    assert parsed.missing_indices == [1, 3]
    assert parsed.extra_indices == [99]
    assert parsed.duplicate_indices == [2]
    assert parsed.reordered is False
    assert parsed.strict_match is False


def test_post_processing_cleaner_removes_duplicates_and_corruption() -> None:
    cleaned = clean_translated_text(
        "hola hola hola\nhola hola hola\n\ufffdQue tal??",
        source_text="Hello there.",
        language="es",
    )

    assert cleaned == "Hola Que tal?"


def test_language_config_supports_dynamic_lookup() -> None:
    config = AppConfig(
        raw={
            "language_settings": {
                "sw": {
                    "label": "Swahili",
                    "rtl": False,
                    "profile": "natural",
                    "aliases": ["swahili"],
                }
            }
        }
    )

    language = config.language_config("swahili")

    assert language.code == "sw"
    assert language.label == "Swahili"
    assert language.profile == "natural"
