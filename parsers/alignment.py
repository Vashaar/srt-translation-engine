from __future__ import annotations

from functools import lru_cache
from difflib import SequenceMatcher

from translator.models import AlignmentResult, ScriptDocument, SubtitleBlock
from translator.text import normalize_text


SEARCH_RADIUS = 5


def align_subtitles_to_script(
    subtitles: list[SubtitleBlock], script: ScriptDocument
) -> list[AlignmentResult]:
    alignments: list[AlignmentResult] = []
    segments = script.segments or [script.normalized_text]
    if not segments:
        return alignments

    segment_count = len(segments)
    subtitle_count = max(len(subtitles) - 1, 1)
    previous_best_index = 0
    for subtitle_position, block in enumerate(subtitles):
        subtitle_text = normalize_text(block.text)
        expected_index = round((subtitle_position / subtitle_count) * max(segment_count - 1, 0))
        anchor_index = previous_best_index if subtitle_position > 0 else expected_index
        center_index = round((anchor_index + expected_index) / 2)
        window_start = max(0, center_index - SEARCH_RADIUS)
        window_end = min(segment_count, center_index + SEARCH_RADIUS + 1)

        best_excerpt = ""
        best_score = 0.0
        best_index = center_index
        for segment_index in range(window_start, window_end):
            segment = segments[segment_index]
            score = _combined_similarity(subtitle_text, segment)
            if score > best_score:
                best_score = score
                best_excerpt = segment
                best_index = segment_index
        previous_best_index = best_index
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


@lru_cache(maxsize=4096)
def _combined_similarity(left: str, right: str) -> float:
    sequence_score = SequenceMatcher(None, left.lower(), right.lower()).ratio()
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        token_overlap = 0.0
    else:
        token_overlap = len(left_tokens & right_tokens) / max(len(left_tokens), 1)
    return round(sequence_score * 0.7 + token_overlap * 0.3, 6)


@lru_cache(maxsize=4096)
def _tokenize(text: str) -> frozenset[str]:
    return frozenset(token.lower() for token in text.split() if token.strip())
