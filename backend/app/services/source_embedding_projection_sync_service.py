from __future__ import annotations

import asyncio
import logging
import os

from database import open_db_session

logger = logging.getLogger(__name__)

DEFAULT_IDLE_POLL_SECONDS = 30.0


async def run_source_embedding_projection_sync() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    logger.info("backend projection sync started")

    poll_seconds = resolve_projection_sync_poll_seconds()
    await asyncio.sleep(0)
    while True:
        await asyncio.to_thread(run_source_embedding_projection_sync_cycle)
        await asyncio.sleep(poll_seconds)


def run_source_embedding_projection_sync_cycle() -> None:
    db = open_db_session()
    try:
        projected_models = _bootstrap_source_embedding_projections(db)
        db.commit()
        if projected_models > 0:
            logger.info("Updated %s source embedding projection model(s)", projected_models)
    except Exception as exception:
        db.rollback()
        logger.exception("Projection sync loop failed: %s", exception)
    finally:
        db.close()


def resolve_projection_sync_poll_seconds() -> float:
    raw_value = os.getenv(
        "BACKEND_PROJECTION_POLL_SECONDS",
        str(DEFAULT_IDLE_POLL_SECONDS),
    ).strip()
    try:
        parsed = float(raw_value)
    except ValueError:
        return DEFAULT_IDLE_POLL_SECONDS
    if parsed <= 0:
        return DEFAULT_IDLE_POLL_SECONDS
    return parsed


def _bootstrap_source_embedding_projections(db):
    # Delay UMAP/sklearn imports until the background sync actually runs.
    from .source_embedding_projection_service import bootstrap_source_embedding_projections

    return bootstrap_source_embedding_projections(db)
