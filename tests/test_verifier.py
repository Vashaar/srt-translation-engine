from translator.models import AlignmentResult, SubtitleBlock, TranslationResult
from verifier.checks import verify_translation
from verifier.validation import validate_and_repair_translation


def test_verifier_flags_leftover_source_text() -> None:
    source = [
        SubtitleBlock(index=1, start="00:00:01,000", end="00:00:03,000", lines=["Hello world"])
    ]
    translated = [
        SubtitleBlock(index=1, start="00:00:01,000", end="00:00:03,000", lines=["Hello world"])
    ]
    alignments = [
        AlignmentResult(
            block_index=1,
            subtitle_text="Hello world",
            script_excerpt="Hello world indeed",
            similarity=0.9,
            used_script_as_truth=True,
        )
    ]
    translations = [
        TranslationResult(translated_text="Hello world", confidence=0.9, notes=[])
    ]

    report = verify_translation(
        language="es",
        source_blocks=source,
        translated_blocks=translated,
        alignments=alignments,
        translations=translations,
        allowed_source_leftovers=[],
        glossary_terms={},
        protected_terms=[],
        rtl=False,
    )

    codes = {issue.code for issue in report.issues}
    assert "leftover_source_text" in codes


def test_verifier_flags_missing_protected_term() -> None:
    source = [
        SubtitleBlock(index=1, start="00:00:01,000", end="00:00:03,000", lines=["Allah is merciful"])
    ]
    translated = [
        SubtitleBlock(index=1, start="00:00:01,000", end="00:00:03,000", lines=["He is merciful"])
    ]
    alignments = [
        AlignmentResult(
            block_index=1,
            subtitle_text="Allah is merciful",
            script_excerpt="Allah is merciful",
            similarity=1.0,
            used_script_as_truth=True,
        )
    ]
    translations = [
        TranslationResult(translated_text="He is merciful", confidence=0.85, notes=[])
    ]

    report = verify_translation(
        language="ur",
        source_blocks=source,
        translated_blocks=translated,
        alignments=alignments,
        translations=translations,
        allowed_source_leftovers=[],
        glossary_terms={},
        protected_terms=["Allah"],
        rtl=False,
    )

    codes = {issue.code for issue in report.issues}
    assert "protected_term_changed" in codes


def test_validation_repairs_structure_and_restores_source_when_needed() -> None:
    source = [
        SubtitleBlock(index=1, start="00:00:01,000", end="00:00:03,000", lines=["Mercy and guidance."]),
        SubtitleBlock(index=2, start="00:00:03,500", end="00:00:05,000", lines=["Peace be upon you."]),
    ]
    translated = [
        SubtitleBlock(index=99, start="00:00:09,000", end="00:00:10,000", lines=[""]),
        SubtitleBlock(
            index=2,
            start="00:00:03,500",
            end="00:00:05,000",
            lines=["This is an extremely long subtitle line that should be rebalanced into something more readable."],
        ),
    ]
    alignments = [
        AlignmentResult(
            block_index=1,
            subtitle_text="Mercy and guidance.",
            script_excerpt="Mercy and guidance.",
            similarity=0.9,
            used_script_as_truth=True,
        ),
        AlignmentResult(
            block_index=2,
            subtitle_text="Peace be upon you.",
            script_excerpt="Peace be upon you.",
            similarity=0.9,
            used_script_as_truth=True,
        ),
    ]
    translations = [
        TranslationResult(translated_text="", confidence=0.1, notes=[]),
        TranslationResult(
            translated_text="This is an extremely long subtitle line that should be rebalanced into something more readable.",
            confidence=0.9,
            notes=[],
        ),
    ]

    validation = validate_and_repair_translation(
        language="es",
        source_blocks=source,
        translated_blocks=translated,
        alignments=alignments,
        translations=translations,
        allowed_source_leftovers=[],
        glossary_terms={},
        protected_terms=[],
        rtl=False,
        max_chars_per_line=40,
        max_lines_per_subtitle=2,
    )

    assert validation.corrected_blocks[0].index == 1
    assert validation.corrected_blocks[0].start == "00:00:01,000"
    assert validation.corrected_blocks[0].text == "Mercy and guidance."
    assert len(validation.corrected_blocks[1].lines) <= 2
    codes = {issue.code for issue in validation.report.issues}
    assert "timing_restored" in codes
    assert "empty_translation_fallback" in codes
