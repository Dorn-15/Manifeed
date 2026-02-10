from pathlib import Path

from app.clients.networking.rss import resolve_rss_icon_file_path
from app.utils import resolve_rss_feeds_repository_path


def get_rss_icon_file_path(icon_url: str) -> Path:
    repository_path = resolve_rss_feeds_repository_path()
    return resolve_rss_icon_file_path(repository_path=repository_path, icon_url=icon_url)
