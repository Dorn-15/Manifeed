from fastapi.responses import FileResponse

from app.clients.networking.rss import resolve_rss_icon_file_path
from app.utils import get_rss_feeds_repository_path


def get_rss_icon_file_path(icon_url: str) -> FileResponse:
    icon_path = resolve_rss_icon_file_path(
        repository_path=get_rss_feeds_repository_path(),
        icon_url=icon_url,
    )

    return FileResponse(
        path=icon_path,
        media_type="image/svg+xml",
        filename=icon_path.name,
    )