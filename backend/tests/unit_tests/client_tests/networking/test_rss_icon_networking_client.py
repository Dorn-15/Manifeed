from pathlib import Path

import pytest

from app.clients.networking.rss import resolve_rss_icon_file_path
from app.errors.rss import RssIconNotFoundError


def test_resolve_rss_icon_file_path_returns_svg_path(tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    icon_path = repository_path / "img" / "theVerge" / "theVerge.svg"
    icon_path.parent.mkdir(parents=True)
    icon_path.write_text("<svg></svg>", encoding="utf-8")

    resolved_icon = resolve_rss_icon_file_path(
        repository_path=repository_path,
        icon_url="theVerge/theVerge.svg",
    )

    assert resolved_icon == icon_path


def test_resolve_rss_icon_file_path_rejects_path_traversal(tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()

    with pytest.raises(RssIconNotFoundError):
        resolve_rss_icon_file_path(
            repository_path=repository_path,
            icon_url="../secrets.svg",
        )
