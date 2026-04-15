from __future__ import annotations

from translator.models import (
    AlignmentResult,
    SubtitleBlock,
    TranslationResult,
    ValidationResult,
    VerificationIssue,
    VerificationReport,
)
from translator.text import rebalance_subtitle_lines
from verifier.checks import verify_translation


def validate_and_repair_translation(
    language: str,
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    alignments: list[AlignmentResult],
    translations: list[TranslationResult],
    allowed_source_leftovers: list[str],
    glossary_terms: dict[str, str],
    protected_terms: list[str],
    rtl: bool,
    max_chars_per_line: int,
    max_lines_per_subtitle: int,
) -> ValidationResult:
    corrected_blocks, repair_issues = _repair_translated_blocks(
        source_blocks=source_blocks,
        translated_blocks=translated_blocks,
        max_chars_per_line=max_chars_per_line,
        max_lines_per_subtitle=max_lines_per_subtitle,
    )
    report = verify_translation(
        language=language,
        source_blocks=source_blocks,
        translated_blocks=corrected_blocks,
        alignments=alignments,
        translations=translations,
        allowed_source_leftovers=allowed_source_leftovers,
        glossary_terms=glossary_terms,
        protected_terms=protected_terms,
        rtl=rtl,
    )
    if repair_issues:
        summary = dict(report.summary)
        summary["repair_count"] = len(repair_issues)
        summary["corrected_blocks"] = len(corrected_blocks)
        report = VerificationReport(
            language=report.language,
            passed=report.passed,
            issues=repair_issues + report.issues,
            summary=summary,
        )
    return ValidationResult(corrected_blocks=corrected_blocks, report=report)


def _repair_translated_blocks(
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    max_chars_per_line: int,
    max_lines_per_subtitle: int,
) -> tuple[list[SubtitleBlock], list[VerificationIssue]]:
    issues: list[VerificationIssue] = []
    corrected_blocks: list[SubtitleBlock] = []

    translated_by_index = {block.index: block for block in translated_blocks}
    if len(translated_blocks) != len(source_blocks):
        issues.append(
            VerificationIssue(
                "high",
                "block_count_repaired",
                None,
                "Translated subtitle block count did not match the source and was repaired.",
            )
        )

    for position, source_block in enumerate(source_blocks):
        translated_block = translated_by_index.get(source_block.index)
        if translated_block is None and position < len(translated_blocks):
            translated_block = translated_blocks[position]
        if translated_block is None:
            issues.append(
                VerificationIssue(
                    "high",
                    "missing_block_restored",
                    source_block.index,
                    "Missing translated block was restored from source text.",
                )
            )
            candidate_text = source_block.text
        else:
            candidate_text = translated_block.text.strip()
            if translated_block.index != source_block.index:
                issues.append(
                    VerificationIssue(
                        "medium",
                        "index_restored",
                        source_block.index,
                        "Subtitle index mismatch was repaired using the source numbering.",
                    )
                )
            if translated_block.start != source_block.start or translated_block.end != source_block.end:
                issues.append(
                    VerificationIssue(
                        "high",
                        "timing_restored",
                        source_block.index,
                        "Subtitle timing was restored to the original source timestamps.",
                    )
                )
            if not candidate_text:
                issues.append(
                    VerificationIssue(
                        "high",
                        "empty_translation_fallback",
                        source_block.index,
                        "Empty translated text was replaced with the source subtitle.",
                    )
                )
                candidate_text = source_block.text

        rebalanced_lines = rebalance_subtitle_lines(
            candidate_text,
            max_chars_per_line=max_chars_per_line,
            max_lines=max_lines_per_subtitle,
        )
        if rebalanced_lines != (translated_block.lines if translated_block else source_block.lines):
            issues.append(
                VerificationIssue(
                    "low",
                    "line_rebalanced",
                    source_block.index,
                    "Subtitle lines were automatically rebalanced for readability.",
                )
            )

        corrected_blocks.append(
            SubtitleBlock(
                index=source_block.index,
                start=source_block.start,
                end=source_block.end,
                lines=rebalanced_lines or list(source_block.lines),
            )
        )

    extra_indices = {block.index for block in translated_blocks} - {block.index for block in source_blocks}
    for index in sorted(extra_indices):
        issues.append(
            VerificationIssue(
                "medium",
                "unexpected_block_dropped",
                index,
                "Unexpected translated block was discarded during validation repair.",
            )
        )
    return corrected_blocks, issues
