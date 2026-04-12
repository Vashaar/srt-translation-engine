from __future__ import annotations

from difflib import SequenceMatcher

from translator.models import AlignmentResult, ScriptDocument, SubtitleBlock
from translator.text import normalize_text


def align_subtitles_to_script(
    subtitles: list[SubtitleBlock], script: ScriptDocument
) -> list[AlignmentResult]:
    alignments: list[AlignmentResult] = []
    segments = script.segments or [script.normalized_text]
    for block in subtitles:
        subtitle_text = normalize_text(block.text)
        best_excerpt = ""
        best_score = 0.0
        for segment in segments:
            score = SequenceMatcher(None, subtitle_text.lower(), segment.lower()).ratio()
            if score > best_score:
                best_score = score
                best_excerpt = segment
        alignments.append(
            AlignmentResult(
                block_index=block.index,
                subtitle_text=block.text,
                script_excerpt=best_excerpt or block.text,
                similarity=best_score,
                used_script_as_truth=best_score >= 0.45,
            )
        )
    return alignments
