from __future__ import annotations

from dataclasses import dataclass
import hashlib
from math import sqrt
from typing import Iterable

from translator.models import AlignmentResult, ScriptDocument, SubtitleBlock
from translator.text import normalize_text


SEARCH_RADIUS = 6
EMBEDDING_DIMENSIONS = 384


@dataclass(slots=True)
class _EmbeddedSegment:
    text: str
    embedding: tuple[float, ...]


class LightweightEmbeddingModel:
    """Fast local embedding model based on hashed token and character n-gram features."""

    def embed(self, text: str) -> tuple[float, ...]:
        normalized = normalize_text(text).lower()
        if not normalized:
            return tuple(0.0 for _ in range(EMBEDDING_DIMENSIONS))

        vector = [0.0] * EMBEDDING_DIMENSIONS
        tokens = [token for token in normalized.split() if token]
        for token in tokens:
            self._add_feature(vector, f"tok:{token}", 1.8)
            for index in range(len(token) - 2):
                self._add_feature(vector, f"tri:{token[index:index + 3]}", 0.7)
            for index in range(len(token) - 3):
                self._add_feature(vector, f"quad:{token[index:index + 4]}", 0.45)

        joined = normalized.replace(" ", "_")
        for index in range(len(joined) - 4):
            self._add_feature(vector, f"ctx:{joined[index:index + 5]}", 0.3)

        magnitude = sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return tuple(0.0 for _ in range(EMBEDDING_DIMENSIONS))
        return tuple(value / magnitude for value in vector)

    @staticmethod
    def _add_feature(vector: list[float], feature: str, weight: float) -> None:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        digest_value = int.from_bytes(digest, "big", signed=False)
        index = digest_value % EMBEDDING_DIMENSIONS
        sign = -1.0 if (digest_value & 1) else 1.0
        vector[index] += weight * sign


def align_subtitles_to_script(
    subtitles: list[SubtitleBlock],
    script: ScriptDocument,
) -> list[AlignmentResult]:
    segments = [segment for segment in (script.segments or [script.normalized_text]) if segment]
    if not subtitles or not segments:
        return []

    model = LightweightEmbeddingModel()
    embedded_segments = [
        _EmbeddedSegment(text=segment, embedding=model.embed(segment))
        for segment in segments
    ]

    alignments: list[AlignmentResult] = []
    segment_count = len(embedded_segments)
    subtitle_count = max(len(subtitles) - 1, 1)
    previous_best_index = 0

    for subtitle_position, block in enumerate(subtitles):
        subtitle_text = normalize_text(block.text)
        subtitle_embedding = model.embed(subtitle_text)
        expected_index = round((subtitle_position / subtitle_count) * max(segment_count - 1, 0))
        anchor_index = previous_best_index if subtitle_position > 0 else expected_index
        center_index = round((anchor_index + expected_index) / 2)
        candidate_indices = _candidate_window(center_index, segment_count)

        best_index = center_index
        best_score = -1.0
        for segment_index in candidate_indices:
            segment = embedded_segments[segment_index]
            score = _cosine_similarity(subtitle_embedding, segment.embedding)
            if score > best_score:
                best_score = score
                best_index = segment_index

        previous_best_index = best_index
        best_segment = embedded_segments[best_index]
        alignments.append(
            AlignmentResult(
                block_index=block.index,
                subtitle_text=block.text,
                script_excerpt=best_segment.text or block.text,
                similarity=round(max(best_score, 0.0), 6),
                used_script_as_truth=best_score >= 0.5,
            )
        )

    return alignments


def _candidate_window(center_index: int, segment_count: int) -> Iterable[int]:
    window_start = max(0, center_index - SEARCH_RADIUS)
    window_end = min(segment_count, center_index + SEARCH_RADIUS + 1)
    return range(window_start, window_end)


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
