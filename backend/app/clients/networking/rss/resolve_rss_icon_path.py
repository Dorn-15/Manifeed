from pathlib import Path

from app.errors.rss import RssIconNotFoundError


def resolve_rss_icon_file_path(repository_path: Path, icon_url: str) -> Path:
    normalized_icon_url = icon_url.strip()
    if not normalized_icon_url:
        raise RssIconNotFoundError("Icon path is empty.")

    relative_icon_path = Path(normalized_icon_url.lstrip("/"))
    if relative_icon_path.is_absolute() or ".." in relative_icon_path.parts:
        raise RssIconNotFoundError("Icon path is invalid.")

    if relative_icon_path.parts and relative_icon_path.parts[0] != "img":
        relative_icon_path = Path("img") / relative_icon_path

    resolved_repository_path = repository_path.resolve()
    resolved_icon_path = (resolved_repository_path / relative_icon_path).resolve()

    try:
        resolved_icon_path.relative_to(resolved_repository_path)
    except ValueError as exception:
        raise RssIconNotFoundError("Icon path is invalid.") from exception

    if resolved_icon_path.suffix.lower() != ".svg":
        raise RssIconNotFoundError("Only svg icons are supported.")

    if not resolved_icon_path.exists() or not resolved_icon_path.is_file():
        raise RssIconNotFoundError(f"Icon not found: {icon_url}")

    return resolved_icon_path
