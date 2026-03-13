from __future__ import annotations

from datetime import datetime
import logging
from collections.abc import Sequence

import numpy as np
from sklearn.decomposition import IncrementalPCA
from sqlalchemy.orm import Session

from app.clients.database import (
    count_source_embedding_projection_inputs,
    get_source_embedding_latest_update_at,
    get_source_embedding_projection_state,
    list_source_embedding_projection_input_batch,
    list_source_embedding_model_names,
    list_source_embedding_projection_inputs,
    upsert_source_embedding_projection_points,
    upsert_source_embedding_projection_state,
)
from app.domain import (
    build_bootstrap_projection_points,
    build_feature_matrix,
    build_projection_points,
    build_projection_preprocessor,
    build_projection_state,
    build_projection_state_from_feature_matrix,
    is_projection_state_current,
    should_fit_projection,
    transform_projection_inputs,
)

DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE = 1000

logger = logging.getLogger(__name__)


def bootstrap_source_embedding_projections(db: Session) -> int:
    projected_models = 0
    for model_name in list_source_embedding_model_names(db):
        if _is_projection_outdated(db, model_name=model_name):
            projected_models += int(_sync_projection_for_model(db, model_name=model_name))
    return projected_models


def sync_source_embedding_projection_for_sources(
    db: Session,
    *,
    model_name: str,
    source_ids: Sequence[int],
) -> bool:
    unique_source_ids = sorted({int(source_id) for source_id in source_ids if int(source_id) > 0})
    if not unique_source_ids:
        return False

    state = get_source_embedding_projection_state(db, model_name=model_name)
    if not is_projection_state_current(state):
        return _sync_projection_for_model(db, model_name=model_name)

    inputs = list_source_embedding_projection_inputs(
        db,
        model_name=model_name,
        source_ids=unique_source_ids,
    )
    if not inputs:
        return False

    points = transform_projection_inputs(inputs=inputs, state=state)
    upsert_source_embedding_projection_points(db, points=points)
    return True


def _sync_projection_for_model(db: Session, *, model_name: str) -> bool:
    total_inputs = count_source_embedding_projection_inputs(db, model_name=model_name)
    if total_inputs <= 0:
        return False

    first_batch = list_source_embedding_projection_input_batch(
        db,
        model_name=model_name,
        limit=min(total_inputs, DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE),
    )
    if not first_batch:
        return False

    if total_inputs <= DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE:
        if not should_fit_projection(first_batch):
            points = build_bootstrap_projection_points(
                inputs=first_batch,
                embedding_model_name=model_name,
            )
            upsert_source_embedding_projection_points(db, points=points)
            db.commit()
            return True

        state, points = build_projection_state(
            inputs=first_batch,
            embedding_model_name=model_name,
        )
        _persist_projection_points_and_state(
            db,
            model_name=model_name,
            state=state,
            points=points,
            total_inputs=total_inputs,
        )
        return True

    logger.info(
        "Rebuilding source embedding projection for model=%s total_embeddings=%s batch_size=%s",
        model_name,
        total_inputs,
        DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE,
    )
    return _rebuild_projection_for_large_model(
        db,
        model_name=model_name,
        total_inputs=total_inputs,
        input_dimension=len(first_batch[0].embedding),
    )


def _rebuild_projection_for_large_model(
    db: Session,
    *,
    model_name: str,
    total_inputs: int,
    input_dimension: int,
) -> bool:
    preprocessor = build_projection_preprocessor(
        input_dimension=input_dimension,
        sample_count=total_inputs,
        batch_size=DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE,
    )
    if preprocessor is not None:
        logger.info(
            "Fitting source embedding preprocessor for model=%s components=%s",
            model_name,
            preprocessor.n_components,
        )
        _fit_projection_preprocessor(
            db,
            model_name=model_name,
            preprocessor=preprocessor,
            total_inputs=total_inputs,
        )

    feature_matrix, source_ids, embedding_updated_ats = _collect_projection_feature_matrix(
        db,
        model_name=model_name,
        total_inputs=total_inputs,
        preprocessor=preprocessor,
    )
    state, coordinates = build_projection_state_from_feature_matrix(
        feature_matrix=feature_matrix,
        embedding_model_name=model_name,
        fitted_sources_count=len(source_ids),
        preprocessor=preprocessor,
    )
    _persist_projection_coordinates_and_state(
        db,
        model_name=model_name,
        state=state,
        coordinates=coordinates,
        source_ids=source_ids,
        embedding_updated_ats=embedding_updated_ats,
        total_inputs=total_inputs,
    )
    return True


def _fit_projection_preprocessor(
    db: Session,
    *,
    model_name: str,
    preprocessor: IncrementalPCA,
    total_inputs: int,
) -> None:
    after_source_id: int | None = None
    fitted_count = 0

    while True:
        inputs = list_source_embedding_projection_input_batch(
            db,
            model_name=model_name,
            limit=DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE,
            after_source_id=after_source_id,
        )
        if not inputs:
            break

        feature_matrix = build_feature_matrix(inputs=inputs)
        preprocessor.partial_fit(feature_matrix)
        fitted_count += len(inputs)
        after_source_id = inputs[-1].source_id

        if fitted_count == total_inputs or fitted_count % 5000 == 0:
            logger.info(
                "Fitted source embedding preprocessor batch for model=%s fitted=%s/%s",
                model_name,
                fitted_count,
                total_inputs,
            )


def _collect_projection_feature_matrix(
    db: Session,
    *,
    model_name: str,
    total_inputs: int,
    preprocessor: IncrementalPCA | None,
) -> tuple[np.ndarray, list[int], list[datetime]]:
    after_source_id: int | None = None
    collected_count = 0
    source_ids: list[int] = []
    embedding_updated_ats: list[datetime] = []
    feature_matrix: np.ndarray | None = None

    while True:
        inputs = list_source_embedding_projection_input_batch(
            db,
            model_name=model_name,
            limit=DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE,
            after_source_id=after_source_id,
        )
        if not inputs:
            break

        batch_features = build_feature_matrix(inputs=inputs, preprocessor=preprocessor)
        batch_count = batch_features.shape[0]
        if feature_matrix is None:
            feature_matrix = np.empty(
                (total_inputs, batch_features.shape[1]),
                dtype=np.float32,
            )

        next_offset = collected_count + batch_count
        feature_matrix[collected_count:next_offset] = batch_features
        source_ids.extend(input_item.source_id for input_item in inputs)
        embedding_updated_ats.extend(input_item.embedding_updated_at for input_item in inputs)
        collected_count = next_offset
        after_source_id = inputs[-1].source_id

        if collected_count == total_inputs or collected_count % 5000 == 0:
            logger.info(
                "Collected source embedding feature batch for model=%s collected=%s/%s",
                model_name,
                collected_count,
                total_inputs,
            )

    if feature_matrix is None:
        return np.empty((0, 0), dtype=np.float32), [], []

    return feature_matrix[:collected_count], source_ids, embedding_updated_ats


def _persist_projection_points_and_state(
    db: Session,
    *,
    model_name: str,
    state,
    points,
    total_inputs: int,
) -> None:
    state.last_embedding_updated_at = get_source_embedding_latest_update_at(db, model_name=model_name)
    upsert_source_embedding_projection_points(db, points=points)
    upsert_source_embedding_projection_state(db, state=state)
    db.commit()
    logger.info(
        "Persisted source embedding projection for model=%s projected=%s/%s",
        model_name,
        len(points),
        total_inputs,
    )


def _persist_projection_coordinates_and_state(
    db: Session,
    *,
    model_name: str,
    state,
    coordinates: np.ndarray,
    source_ids: list[int],
    embedding_updated_ats: list[datetime],
    total_inputs: int,
) -> None:
    projected_count = 0

    for start in range(0, total_inputs, DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE):
        stop = min(start + DEFAULT_SOURCE_EMBEDDING_PROJECTION_BATCH_SIZE, total_inputs)
        points = build_projection_points(
            source_ids=source_ids[start:stop],
            embedding_updated_ats=embedding_updated_ats[start:stop],
            coordinates=coordinates[start:stop],
            embedding_model_name=model_name,
            projection_version=state.projection_version,
        )
        upsert_source_embedding_projection_points(db, points=points)
        projected_count = stop

        if projected_count == total_inputs or projected_count % 5000 == 0:
            logger.info(
                "Prepared source embedding layout batch for model=%s projected=%s/%s",
                model_name,
                projected_count,
                total_inputs,
            )

    state.last_embedding_updated_at = get_source_embedding_latest_update_at(db, model_name=model_name)
    upsert_source_embedding_projection_state(db, state=state)
    db.commit()


def _is_projection_outdated(db: Session, *, model_name: str) -> bool:
    state = get_source_embedding_projection_state(db, model_name=model_name)
    if not is_projection_state_current(state):
        return True

    latest_embedding_updated_at = get_source_embedding_latest_update_at(db, model_name=model_name)
    if latest_embedding_updated_at is None:
        return False
    if state is None or state.last_embedding_updated_at is None:
        return True
    return latest_embedding_updated_at > state.last_embedding_updated_at
