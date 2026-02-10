from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from .custom_exceptions import (
    RssCatalogParseError,
    RssIconNotFoundError,
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
