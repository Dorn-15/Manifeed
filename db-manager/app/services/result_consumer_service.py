from __future__ import annotations

import asyncio
import logging

from app.clients.queue.redis_queue_client import (
    ack_worker_result,
    DEFAULT_REDIS_QUEUE_CHECK,
    DEFAULT_REDIS_QUEUE_INGEST,
    DEFAULT_REDIS_QUEUE_ERRORS,
    ensure_consumer_groups,
    read_worker_results,
)
from app.database import get_db_session
from app.domain import resolve_queue_kind
from app.schemas import WorkerResultSchema
from app.errors import DBManagerQueueError
from .result_persistence_service import persist_worker_result

logger = logging.getLogger(__name__)


async def run_result_consumer() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await ensure_consumer_groups()
    logger.info("db_manager started")

    while True:
        try:
            messages = await read_worker_results(count=10, block_ms=5000)
            if not messages:
                continue

            for stream_name, message_id, payload_raw in messages:
                await _process_result_message(
                    stream_name=stream_name,
                    message_id=message_id,
                    payload_raw=payload_raw,
                )
        except DBManagerQueueError as exception:
            logger.warning("db_manager queue unavailable: %s", exception)
            await asyncio.sleep(1.0)
        except Exception as exception:
            logger.exception("db_manager loop error: %s", exception)
            await asyncio.sleep(1.0)


async def _process_result_message(
    *,
    stream_name: str,
    message_id: str,
    payload_raw: dict,
) -> None:
    try:
        payload = WorkerResultSchema.model_validate(payload_raw)
    except Exception as exception:
        logger.error("Invalid worker result payload for %s: %s", message_id, exception)
        await ack_worker_result(stream_name, message_id)
        return

    queue_kind = resolve_queue_kind(
        stream_name,
        check_stream=DEFAULT_REDIS_QUEUE_CHECK,
        ingest_stream=DEFAULT_REDIS_QUEUE_INGEST,
        error_stream=DEFAULT_REDIS_QUEUE_ERRORS,
    )

    db = get_db_session()
    try:
        persist_worker_result(
            db,
            payload=payload,
            queue_kind=queue_kind,
        )
        db.commit()
    except Exception as exception:
        db.rollback()
        logger.exception("Failed to persist worker result %s: %s", message_id, exception)
        return
    finally:
        db.close()

    await ack_worker_result(stream_name, message_id)
