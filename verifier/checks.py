from __future__ import annotations

import re
from collections import defaultdict

from translator.models import AlignmentResult, SubtitleBlock, TranslationResult, VerificationIssue, VerificationReport
from translator.text import contains_substantial_source_text


def verify_translation(
    language: str,
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    alignments: list[AlignmentResult],
    translations: list[TranslationResult],
    allowed_source_leftovers: list[str],
    glossary_terms: dict[str, str],
    protected_terms: list[str],
    rtl: bool,
) -> VerificationReport:
    issues: list[VerificationIssue] = []
    issues.extend(_check_structure(source_blocks, translated_blocks))
    issues.extend(
        _check_completeness(source_blocks, translated_blocks, allowed_source_leftovers)
    )
    issues.extend(_check_consistency(source_blocks, translated_blocks))
    issues.extend(
        _check_protected_terms(
            source_blocks=source_blocks,
            translated_blocks=translated_blocks,
            glossary_terms=glossary_terms,
            protected_terms=protected_terms,
        )
    )
    issues.extend(_check_semantic_fidelity(alignments, translations))
    issues.extend(_check_linguistic_quality(translated_blocks, translations))
    issues.extend(_check_readability(translated_blocks))
    if rtl:
        issues.extend(_check_rtl(language, translated_blocks))

    summary = {
        "source_blocks": len(source_blocks),
        "translated_blocks": len(translated_blocks),
        "issue_count": len(issues),
        "high_severity_count": sum(1 for item in issues if item.severity == "high"),
        "uncertainty_count": sum(
            1
            for item in issues
            if item.code in {"weak_script_alignment", "low_model_confidence", "provider_uncertainty"}
        ),
        "average_confidence": round(
            sum(result.confidence for result in translations) / max(len(translations), 1),
            3,
        ),
        "verification_notice": (
            "Verification uses layered heuristics and uncertainty reporting. "
            "It does not prove semantic correctness."
        ),
    }
    passed = not any(issue.severity == "high" for issue in issues)
    return VerificationReport(language=language, passed=passed, issues=issues, summary=summary)


def _check_structure(
    source_blocks: list[SubtitleBlock], translated_blocks: list[SubtitleBlock]
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    for expected, translated in zip(source_blocks, translated_blocks, strict=False):
        if expected.index != translated.index:
            issues.append(
                VerificationIssue("high", "numbering_sequence", translated.index, "Subtitle numbering changed.")
            )
        if expected.start != translated.start or expected.end != translated.end:
            issues.append(
                VerificationIssue("high", "timing_changed", translated.index, "Subtitle timing changed unexpectedly.")
            )
        if not translated.lines:
            issues.append(
                VerificationIssue("high", "empty_block", translated.index, "Translated block is empty.")
            )
    return issues


def _check_completeness(
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    allowed_source_leftovers: list[str],
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    if len(source_blocks) != len(translated_blocks):
        issues.append(
            VerificationIssue(
                "high",
                "block_count_mismatch",
                None,
                "Translated subtitle block count does not match the source SRT.",
            )
        )
    for source, translated in zip(source_blocks, translated_blocks, strict=False):
        if contains_substantial_source_text(translated.text, source.text, allowed_source_leftovers):
            issues.append(
                VerificationIssue(
                    "medium",
                    "leftover_source_text",
                    translated.index,
                    "Translated text still contains substantial source-language wording.",
                )
            )
    return issues


def _check_consistency(
    source_blocks: list[SubtitleBlock], translated_blocks: list[SubtitleBlock]
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    repeated_sources: dict[str, list[str]] = defaultdict(list)
    for source, translated in zip(source_blocks, translated_blocks, strict=False):
        key = source.text.strip().lower()
        repeated_sources[key].append(translated.text.strip())
    for source_text, variants in repeated_sources.items():
        unique_variants = {variant for variant in variants if variant}
        if len(unique_variants) > 1 and len(variants) > 1:
            issues.append(
                VerificationIssue(
                    "low",
                    "inconsistent_repetition",
                    None,
                    f"Repeated source segment has multiple translations: {source_text[:60]}",
                )
            )
    return issues


def _check_protected_terms(
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    glossary_terms: dict[str, str],
    protected_terms: list[str],
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    protected_lookup = {term.lower(): term for term in protected_terms}
    glossary_lookup = {source.lower(): target for source, target in glossary_terms.items()}
    for source, translated in zip(source_blocks, translated_blocks, strict=False):
        source_lower = source.text.lower()
        translated_lower = translated.text.lower()
        for protected_lower, protected_original in protected_lookup.items():
            if protected_lower in source_lower and protected_lower not in translated_lower:
                issues.append(
                    VerificationIssue(
                        "medium",
                        "protected_term_changed",
                        translated.index,
                        f"Protected term '{protected_original}' was present in the source but not preserved in the translation.",
                    )
                )
        for glossary_source, glossary_target in glossary_lookup.items():
            if glossary_source in source_lower:
                expected = str(glossary_target).lower()
                if expected not in translated_lower and glossary_source not in translated_lower:
                    issues.append(
                        VerificationIssue(
                            "medium",
                            "glossary_term_missing",
                            translated.index,
                            f"Glossary-backed term '{glossary_source}' was not found as '{glossary_target}' in the translation.",
                        )
                    )
    return issues


def _check_semantic_fidelity(
    alignments: list[AlignmentResult], translations: list[TranslationResult]
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    for alignment, result in zip(alignments, translations, strict=False):
        if alignment.similarity < 0.25:
            issues.append(
                VerificationIssue(
                    "medium",
                    "weak_script_alignment",
                    alignment.block_index,
                    "Subtitle block aligned weakly to the source script; meaning may need review.",
                )
            )
        if result.confidence < 0.5:
            issues.append(
                VerificationIssue(
                    "medium",
                    "low_model_confidence",
                    alignment.block_index,
                    "Translation confidence is low.",
                )
            )
        if result.translated_text and alignment.subtitle_text:
            source_len = len(alignment.subtitle_text.split())
            translated_len = len(result.translated_text.split())
            if source_len > 0 and translated_len / source_len < 0.45:
                issues.append(
                    VerificationIssue(
                        "medium",
                        "possible_omission",
                        alignment.block_index,
                        "Translated block is much shorter than the source and may omit meaning.",
                    )
                )
    return issues


def _check_linguistic_quality(
    translated_blocks: list[SubtitleBlock], translations: list[TranslationResult]
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    repeated_punctuation = re.compile(r"[!?.,;:]{3,}")
    for block, result in zip(translated_blocks, translations, strict=False):
        if repeated_punctuation.search(block.text):
            issues.append(
                VerificationIssue(
                    "low",
                    "punctuation_noise",
                    block.index,
                    "Unusual punctuation density detected.",
                )
            )
        if any("uncertain" in note.lower() for note in result.notes):
            issues.append(
                VerificationIssue(
                    "medium",
                    "provider_uncertainty",
                    block.index,
                    "Provider marked this segment as uncertain.",
                )
            )
    return issues


def _check_readability(translated_blocks: list[SubtitleBlock]) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    for block in translated_blocks:
        for line in block.lines:
            if len(line) > 52:
                issues.append(
                    VerificationIssue(
                        "low",
                        "long_line",
                        block.index,
                        f"Subtitle line exceeds recommended length ({len(line)} chars).",
                    )
                )
        if len(block.lines) > 2:
            issues.append(
                VerificationIssue(
                    "low",
                    "too_many_lines",
                    block.index,
                    "Subtitle block has more than two lines.",
                )
            )
    return issues


def _check_rtl(language: str, translated_blocks: list[SubtitleBlock]) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    rtl_chars = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
    for block in translated_blocks:
        if not rtl_chars.search(block.text):
            issues.append(
                VerificationIssue(
                    "medium",
                    "rtl_script_missing",
                    block.index,
                    f"Expected RTL script characters for {language}, but none were detected.",
                )
            )
    return issues
