from __future__ import annotations

import math

from app.schemas.sources import RssSourceEmbeddingSimilarityCandidateSchema


def rank_source_embedding_neighbors(
    *,
    source: RssSourceEmbeddingSimilarityCandidateSchema,
    candidates: list[RssSourceEmbeddingSimilarityCandidateSchema],
    limit: int,
) -> list[tuple[RssSourceEmbeddingSimilarityCandidateSchema, float]]:
    ranked_neighbors: list[tuple[RssSourceEmbeddingSimilarityCandidateSchema, float]] = []
    for candidate in candidates:
        if candidate.source_id == source.source_id:
            continue

        similarity = _cosine_similarity(source.embedding, candidate.embedding)
        ranked_neighbors.append((candidate, similarity))

    ranked_neighbors.sort(
        key=lambda item: (
            -item[1],
            -item[0].source_id,
        )
    )
    return ranked_neighbors[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot_product = 0.0
    left_norm = 0.0
    right_norm = 0.0

    for left_value, right_value in zip(left, right, strict=True):
        dot_product += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value

    if left_norm <= 0 or right_norm <= 0:
        return 0.0

    return dot_product / math.sqrt(left_norm * right_norm)
