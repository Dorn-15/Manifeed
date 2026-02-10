import os
from logging.config import dictConfig
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors.rss import (
    RssCatalogParseError,
    RssIconNotFoundError,
    RssRepositorySyncError,
    # Exception handlers
    rss_catalog_parse_error_handler,
    rss_icon_not_found_error_handler,
    rss_repository_sync_error_handler,
)

from app.routers import (
    health_router,
    rss_router,
)


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


def create_app() -> FastAPI:
    _configure_app_logging()
    app = FastAPI(title="Manifeed API")

    cors_origins, allow_credentials = _parse_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(rss_router)
    app.add_exception_handler(
        RssRepositorySyncError,
        rss_repository_sync_error_handler,
    )
    app.add_exception_handler(
        RssCatalogParseError,
        rss_catalog_parse_error_handler,
    )
    app.add_exception_handler(
        RssIconNotFoundError,
        rss_icon_not_found_error_handler,
    )

    return app


app = create_app()
