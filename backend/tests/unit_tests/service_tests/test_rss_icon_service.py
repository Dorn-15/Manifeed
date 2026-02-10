from pathlib import Path

import app.services.rss_icon_service as rss_icon_service_module


def test_get_rss_icon_file_path_resolves_from_repository(monkeypatch, tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    icon_path = repository_path / "img" / "theVerge" / "theVerge.svg"
    icon_path.parent.mkdir(parents=True)
    icon_path.write_text("<svg></svg>", encoding="utf-8")

    monkeypatch.setattr(
        rss_icon_service_module,
        "resolve_rss_feeds_repository_path",
        lambda: repository_path,
    )

    resolved_icon = rss_icon_service_module.get_rss_icon_file_path("theVerge/theVerge.svg")

    assert resolved_icon == icon_path
