from __future__ import annotations

import csv
import json
from pathlib import Path

from translator.models import AlignmentResult, SubtitleBlock, TranslationResult, VerificationReport


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_srt(path: Path, subtitles: list[SubtitleBlock]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for block in subtitles:
            handle.write(f"{block.index}\n")
            handle.write(f"{block.start} --> {block.end}\n")
            handle.write("\n".join(block.lines).rstrip())
            handle.write("\n\n")


def write_report(path: Path, report: VerificationReport) -> None:
    payload = {
        "language": report.language,
        "passed": report.passed,
        "summary": report.summary,
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "block_index": issue.block_index,
                "message": issue.message,
            }
            for issue in report.issues
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_review_csv(
    path: Path,
    source_blocks: list[SubtitleBlock],
    translated_blocks: list[SubtitleBlock],
    alignments: list[AlignmentResult],
    translations: list[TranslationResult],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "index",
                "source_subtitle",
                "script_reference",
                "translated_subtitle",
                "confidence",
                "notes",
            ]
        )
        for source, translated, alignment, result in zip(
            source_blocks, translated_blocks, alignments, translations, strict=True
        ):
            writer.writerow(
                [
                    source.index,
                    source.text,
                    alignment.script_excerpt,
                    translated.text,
                    f"{result.confidence:.3f}",
                    " | ".join(result.notes),
                ]
            )


def write_flags(path: Path, report: VerificationReport) -> None:
    with path.open("w", encoding="utf-8") as handle:
        if not report.issues:
            handle.write("No issues flagged.\n")
            return
        for issue in report.issues:
            location = f"Block {issue.block_index}" if issue.block_index else "Global"
            handle.write(
                f"[{issue.severity.upper()}] {location} {issue.code}: {issue.message}\n"
            )
