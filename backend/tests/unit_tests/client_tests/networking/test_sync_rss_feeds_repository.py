from pathlib import Path
import importlib
from types import SimpleNamespace

import pytest

from app.errors.rss import RssRepositorySyncError

sync_repository_module = importlib.import_module(
    "app.clients.networking.rss.sync_rss_feeds_repository"
)


def test_sync_repository_returns_git_revision_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"

    monkeypatch.setattr(
        sync_repository_module,
        "pull_or_clone",
        lambda repository_url, repository_path, branch: SimpleNamespace(
            action="update",
            previous_revision="rev-1",
            current_revision="rev-2",
        ),
    )

    result = sync_repository_module.sync_rss_feeds_repository(
        repository_url="https://github.com/example/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert result.action == "update"
    assert result.repository_path == str(repository_path)
    assert result.previous_revision == "rev-1"
    assert result.current_revision == "rev-2"
    assert result.changed_files == []


def test_sync_repository_raises_when_git_sync_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"

    monkeypatch.setattr(
        sync_repository_module,
        "pull_or_clone",
        lambda repository_url, repository_path, branch: (_ for _ in ()).throw(
            RssRepositorySyncError("dns failure")
        ),
    )
    with pytest.raises(RssRepositorySyncError, match="dns failure"):
        sync_repository_module.sync_rss_feeds_repository(
            repository_url="https://github.com/example/rss_feeds",
            repository_path=repository_path,
            branch="main",
        )
