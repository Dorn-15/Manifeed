from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from .custom_exceptions import (
    RssCatalogParseError,
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
    RssIconNotFoundError,
    RssJobAlreadyRunningError,
    RssRepositorySyncError,
)


def rss_repository_sync_error_handler(
    _: Request,
    exception: RssRepositorySyncError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"message": str(exception)},
    )


def rss_catalog_parse_error_handler(
    _: Request,
    exception: RssCatalogParseError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": str(exception)},
    )


def rss_icon_not_found_error_handler(
    _: Request,
    exception: RssIconNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exception)},
    )


def rss_feed_not_found_error_handler(
    _: Request,
    exception: RssFeedNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exception)},
    )


def rss_company_not_found_error_handler(
    _: Request,
    exception: RssCompanyNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exception)},
    )


def rss_feed_toggle_forbidden_error_handler(
    _: Request,
    exception: RssFeedToggleForbiddenError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": str(exception)},
    )


def rss_job_already_running_error_handler(
    _: Request,
    exception: RssJobAlreadyRunningError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": str(exception)},
    )
