from __future__ import annotations

import logging
from pathlib import Path
import time

from alembic import command
from alembic.config import Config

from app.errors import DBManagerError

logger = logging.getLogger(__name__)

DEFAULT_MIGRATION_MAX_ATTEMPTS = 5
DEFAULT_MIGRATION_RETRY_DELAY_SECONDS = 2.0


def run_db_migrations(
    *,
    max_attempts: int = DEFAULT_MIGRATION_MAX_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_MIGRATION_RETRY_DELAY_SECONDS,
) -> None:
    if max_attempts <= 0:
        raise DBManagerError("max_attempts must be greater than zero")

    alembic_config = _build_alembic_config()

    for attempt in range(1, max_attempts + 1):
        try:
            command.upgrade(alembic_config, "head")
            return
        except Exception as exception:
            if attempt >= max_attempts:
                raise DBManagerError(
                    f"Unable to run database migrations after {max_attempts} attempts: {exception}"
                ) from exception
            logger.warning(
                "Database migration attempt %s/%s failed: %s",
                attempt,
                max_attempts,
                exception,
            )
            time.sleep(retry_delay_seconds)


def _build_alembic_config() -> Config:
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini_path = project_root / "alembic.ini"
    script_location = project_root / "alembic"

    if not alembic_ini_path.exists():
        raise DBManagerError(f"Alembic config file not found: {alembic_ini_path}")
    if not script_location.exists():
        raise DBManagerError(f"Alembic script location not found: {script_location}")

    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(script_location))
    return config
