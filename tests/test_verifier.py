from translator.models import AlignmentResult, SubtitleBlock, TranslationResult
from verifier.checks import verify_translation


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
