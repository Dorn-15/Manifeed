from pathlib import Path
from fastapi.responses import FileResponse

import app.services.rss.rss_icon_service as rss_icon_service_module


def test_get_rss_icon_file_path_uses_repository_path(monkeypatch, tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    expected_icon_path = repository_path / "img" / "example" / "icon.svg"
    calls: list[tuple[Path, str]] = []

    monkeypatch.setattr(
        rss_icon_service_module,
        "get_rss_feeds_repository_path",
        lambda: repository_path,
    )

    def fake_resolve(*, repository_path: Path, icon_url: str) -> Path:
        calls.append((repository_path, icon_url))
        return expected_icon_path

    monkeypatch.setattr(
        rss_icon_service_module,
        "resolve_rss_icon_file_path",
        fake_resolve,
    )

    result = rss_icon_service_module.get_rss_icon_file_path("example/icon.svg")

    assert isinstance(result, FileResponse)
    assert Path(result.path) == expected_icon_path
    assert result.media_type == "image/svg+xml"
    assert calls == [(repository_path, "example/icon.svg")]
