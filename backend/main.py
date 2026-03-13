import asyncio
from contextlib import asynccontextmanager, suppress
import os
from logging.config import dictConfig
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors.rss import (
    RssCatalogParseError,
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
    RssIconNotFoundError,
    RssJobAlreadyRunningError,
    RssJobEnqueueError,
    RssRepositorySyncError,
    # Exception handlers
    rss_catalog_parse_error_handler,
    rss_company_not_found_error_handler,
    rss_feed_not_found_error_handler,
    rss_feed_toggle_forbidden_error_handler,
    rss_icon_not_found_error_handler,
    rss_job_already_running_error_handler,
    rss_job_enqueue_error_handler,
    rss_repository_sync_error_handler,
)

from app.routers import (
    health_router,
    internal_workers_router,
    jobs_router,
    rss_router,
    sources_router,
)
from app.services.migration_service import run_db_migrations
from app.services.source_embedding_projection_sync_service import run_source_embedding_projection_sync


def _configure_app_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "app_default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s %(message)s",
                    "use_colors": None,
                }
            },
            "handlers": {
                "app_default": {
                    "class": "logging.StreamHandler",
                    "formatter": "app_default",
                    "stream": "ext://sys.stderr",
                }
            },
            "loggers": {
                "app": {
                    "handlers": ["app_default"],
                    "level": "INFO",
                    "propagate": False,
                }
            },
        }
    )


def _parse_cors_origins() -> Tuple[List[str], bool]:
    raw_origins = os.getenv("CORS_ORIGINS", "")
    if raw_origins.strip() == "*":
        return ["*"], False

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if origins:
        return origins, True
    return ["http://localhost:3000", "http://localhost:3001"], True


@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    if _startup_tasks_disabled():
        yield
        return
    run_db_migrations()
    projection_sync_task = asyncio.create_task(run_source_embedding_projection_sync())
    try:
        yield
    finally:
        projection_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await projection_sync_task


def create_app() -> FastAPI:
    _configure_app_logging()
    app = FastAPI(title="Manifeed API", lifespan=_app_lifespan)

    cors_origins, allow_credentials = _parse_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(internal_workers_router)
    app.include_router(jobs_router)
    app.include_router(rss_router)
    app.include_router(sources_router)

    exception_handlers = (
        (RssRepositorySyncError, rss_repository_sync_error_handler),
        (RssCatalogParseError, rss_catalog_parse_error_handler),
        (RssIconNotFoundError, rss_icon_not_found_error_handler),
        (RssFeedNotFoundError, rss_feed_not_found_error_handler),
        (RssCompanyNotFoundError, rss_company_not_found_error_handler),
        (RssFeedToggleForbiddenError, rss_feed_toggle_forbidden_error_handler),
        (RssJobAlreadyRunningError, rss_job_already_running_error_handler),
        (RssJobEnqueueError, rss_job_enqueue_error_handler),
    )
    for exc_cls, handler in exception_handlers:
        app.add_exception_handler(exc_cls, handler)

    return app


def _startup_tasks_disabled() -> bool:
    raw_value = os.getenv("MANIFEED_DISABLE_STARTUP_TASKS", "").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


app = create_app()
