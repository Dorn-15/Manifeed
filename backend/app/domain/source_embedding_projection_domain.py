from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import pickle
from typing import Any

import numpy as np
from sklearn.decomposition import IncrementalPCA
from umap import UMAP

from app.schemas.source_embedding_projection_schema import (
    SourceEmbeddingProjectionInputSchema,
    SourceEmbeddingProjectionPointSchema,
    SourceEmbeddingProjectionStateSchema,
)

DEFAULT_SOURCE_EMBEDDING_PROJECTION_VERSION = "ipca_umap_cosine_v3"
DEFAULT_SOURCE_EMBEDDING_PROJECTOR_KIND = "ipca_umap"
DEFAULT_SOURCE_EMBEDDING_N_NEIGHBORS = 32
DEFAULT_SOURCE_EMBEDDING_PREPROCESSOR_COMPONENTS = 128
MIN_SOURCE_EMBEDDINGS_FOR_PREPROCESSOR = 2048
MIN_SOURCE_EMBEDDINGS_FOR_UMAP = 3


@dataclass(slots=True)
class SourceEmbeddingProjector:
    reducer: UMAP
    preprocessor: IncrementalPCA | None = None

    def transform(self, embedding_matrix: np.ndarray) -> np.ndarray:
        feature_matrix = _build_feature_matrix_from_embedding_matrix(
            embedding_matrix,
            preprocessor=self.preprocessor,
        )
        return self.reducer.transform(feature_matrix)


def build_projection_state(
    *,
    inputs: list[SourceEmbeddingProjectionInputSchema],
    embedding_model_name: str,
) -> tuple[SourceEmbeddingProjectionStateSchema, list[SourceEmbeddingProjectionPointSchema]]:
    source_ids = [input_item.source_id for input_item in inputs]
    embedding_updated_ats = [input_item.embedding_updated_at for input_item in inputs]
    feature_matrix = build_feature_matrix(inputs=inputs)
    state, coordinates = build_projection_state_from_feature_matrix(
        feature_matrix=feature_matrix,
        embedding_model_name=embedding_model_name,
        fitted_sources_count=len(source_ids),
        preprocessor=None,
    )
    return state, build_projection_points(
        source_ids=source_ids,
        embedding_updated_ats=embedding_updated_ats,
        coordinates=coordinates,
        embedding_model_name=embedding_model_name,
    )


def build_projection_preprocessor(
    *,
    input_dimension: int,
    sample_count: int,
    batch_size: int,
) -> IncrementalPCA | None:
    if sample_count < MIN_SOURCE_EMBEDDINGS_FOR_PREPROCESSOR:
        return None

    component_count = min(
        DEFAULT_SOURCE_EMBEDDING_PREPROCESSOR_COMPONENTS,
        input_dimension,
        sample_count - 1,
        max(2, batch_size - 1),
    )
    if component_count < 2 or component_count >= input_dimension:
        return None

    return IncrementalPCA(
        n_components=component_count,
        batch_size=max(batch_size, component_count),
    )


def build_feature_matrix(
    *,
    inputs: list[SourceEmbeddingProjectionInputSchema],
    preprocessor: IncrementalPCA | None = None,
) -> np.ndarray:
    return _build_feature_matrix_from_embedding_matrix(
        _build_embedding_matrix(inputs),
        preprocessor=preprocessor,
    )


def build_projection_state_from_feature_matrix(
    *,
    feature_matrix: np.ndarray,
    embedding_model_name: str,
    fitted_sources_count: int,
    preprocessor: IncrementalPCA | None,
) -> tuple[SourceEmbeddingProjectionStateSchema, np.ndarray]:
    projector = SourceEmbeddingProjector(
        reducer=_build_reducer(sample_count=fitted_sources_count),
        preprocessor=preprocessor,
    )
    coordinates = projector.reducer.fit_transform(feature_matrix)
    state = SourceEmbeddingProjectionStateSchema(
        embedding_model_name=embedding_model_name,
        projection_version=DEFAULT_SOURCE_EMBEDDING_PROJECTION_VERSION,
        projector_kind=DEFAULT_SOURCE_EMBEDDING_PROJECTOR_KIND,
        projector_state=pickle.dumps(projector, protocol=pickle.HIGHEST_PROTOCOL),
        fitted_sources_count=fitted_sources_count,
    )
    return state, coordinates


def build_projection_points(
    *,
    source_ids: list[int],
    embedding_updated_ats: list[datetime],
    coordinates: np.ndarray,
    embedding_model_name: str,
    projection_version: str = DEFAULT_SOURCE_EMBEDDING_PROJECTION_VERSION,
) -> list[SourceEmbeddingProjectionPointSchema]:
    points: list[SourceEmbeddingProjectionPointSchema] = []
    for source_id, embedding_updated_at, coordinate in zip(
        source_ids,
        embedding_updated_ats,
        coordinates,
        strict=True,
    ):
        points.append(
            SourceEmbeddingProjectionPointSchema(
                source_id=source_id,
                embedding_model_name=embedding_model_name,
                projection_version=projection_version,
                x=float(coordinate[0]),
                y=float(coordinate[1]),
                embedding_updated_at=embedding_updated_at,
            )
        )
    return points


def transform_projection_inputs(
    *,
    inputs: list[SourceEmbeddingProjectionInputSchema],
    state: SourceEmbeddingProjectionStateSchema,
) -> list[SourceEmbeddingProjectionPointSchema]:
    projector = _deserialize_projector(state.projector_state)
    coordinates = projector.transform(_build_embedding_matrix(inputs))
    return build_projection_points(
        source_ids=[input_item.source_id for input_item in inputs],
        embedding_updated_ats=[input_item.embedding_updated_at for input_item in inputs],
        coordinates=coordinates,
        embedding_model_name=state.embedding_model_name,
        projection_version=state.projection_version,
    )


def build_bootstrap_projection_points(
    *,
    inputs: list[SourceEmbeddingProjectionInputSchema],
    embedding_model_name: str,
) -> list[SourceEmbeddingProjectionPointSchema]:
    if not inputs:
        return []

    if len(inputs) == 1:
        coordinates = np.asarray([[0.0, 0.0]], dtype=np.float64)
    else:
        coordinates = np.asarray(
            [
                (-0.75 if index == 0 else 0.75, 0.0)
                for index in range(len(inputs))
            ],
            dtype=np.float64,
        )

    return build_projection_points(
        source_ids=[input_item.source_id for input_item in inputs],
        embedding_updated_ats=[input_item.embedding_updated_at for input_item in inputs],
        coordinates=coordinates,
        embedding_model_name=embedding_model_name,
    )


def is_projection_state_current(state: SourceEmbeddingProjectionStateSchema | None) -> bool:
    if state is None:
        return False
    return (
        state.projection_version == DEFAULT_SOURCE_EMBEDDING_PROJECTION_VERSION
        and state.projector_kind == DEFAULT_SOURCE_EMBEDDING_PROJECTOR_KIND
    )


def should_fit_projection(inputs: list[SourceEmbeddingProjectionInputSchema]) -> bool:
    return len(inputs) >= MIN_SOURCE_EMBEDDINGS_FOR_UMAP


def _build_reducer(*, sample_count: int) -> UMAP:
    n_neighbors = min(DEFAULT_SOURCE_EMBEDDING_N_NEIGHBORS, sample_count - 1)
    return UMAP(
        n_components=2,
        metric="cosine",
        min_dist=0.02,
        spread=1.0,
        n_neighbors=max(2, n_neighbors),
        init="spectral",
        low_memory=True,
        local_connectivity=2.0,
        negative_sample_rate=8,
        random_state=42,
        transform_seed=42,
    )


def _build_embedding_matrix(inputs: list[SourceEmbeddingProjectionInputSchema]) -> np.ndarray:
    return np.asarray([input_item.embedding for input_item in inputs], dtype=np.float32)


def _build_feature_matrix_from_embedding_matrix(
    embedding_matrix: np.ndarray,
    *,
    preprocessor: IncrementalPCA | None,
) -> np.ndarray:
    normalized_matrix = _normalize_embedding_matrix(embedding_matrix)
    if preprocessor is None:
        return normalized_matrix

    reduced_matrix = np.asarray(
        preprocessor.transform(normalized_matrix),
        dtype=np.float32,
    )
    return _normalize_embedding_matrix(reduced_matrix)


def _normalize_embedding_matrix(embedding_matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embedding_matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0.0, 1.0, norms)
    return np.asarray(embedding_matrix / safe_norms, dtype=np.float32)


def _deserialize_projector(payload: bytes) -> Any:
    projector = pickle.loads(payload)
    if isinstance(projector, UMAP):
        return SourceEmbeddingProjector(reducer=projector)
    if not hasattr(projector, "transform"):
        raise TypeError("Stored source embedding projector does not support transform()")
    return projector
