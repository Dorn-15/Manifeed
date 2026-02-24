from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_toggle_service as rss_toggle_service_module
from app.errors.rss import (
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
)


def test_toggle_rss_feed_enabled_raises_when_feed_is_missing(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(rss_toggle_service_module, "get_rss_feed_by_id", lambda _db, _feed_id: None)

    with pytest.raises(RssFeedNotFoundError, match="RSS feed 3 not found"):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=3, enabled=False)


def test_toggle_rss_feed_enabled_returns_current_value_when_unchanged(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=8, enabled=True, company=SimpleNamespace(name="ACME", enabled=False))
    monkeypatch.setattr(rss_toggle_service_module, "get_rss_feed_by_id", lambda _db, _feed_id: feed)

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=8, enabled=True)

    assert result.feed_id == 8
    assert result.enabled is True
    db.commit.assert_not_called()


def test_toggle_rss_feed_enabled_raises_when_company_is_disabled(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=9, enabled=True, company=SimpleNamespace(name="ACME", enabled=False))
    monkeypatch.setattr(rss_toggle_service_module, "get_rss_feed_by_id", lambda _db, _feed_id: feed)

    with pytest.raises(RssFeedToggleForbiddenError, match="Cannot toggle feed 9"):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=9, enabled=False)


def test_toggle_rss_feed_enabled_updates_and_commits(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=10, enabled=True, company=SimpleNamespace(name="ACME", enabled=True))
    monkeypatch.setattr(rss_toggle_service_module, "get_rss_feed_by_id", lambda _db, _feed_id: feed)
    monkeypatch.setattr(rss_toggle_service_module, "set_rss_feed_enabled", lambda _db, feed_id, enabled: True)

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=10, enabled=False)

    assert result.feed_id == 10
    assert result.enabled is False
    db.commit.assert_called_once()


def test_toggle_rss_feed_enabled_rolls_back_when_update_returns_false(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=11, enabled=True, company=SimpleNamespace(name="ACME", enabled=True))
    monkeypatch.setattr(rss_toggle_service_module, "get_rss_feed_by_id", lambda _db, _feed_id: feed)
    monkeypatch.setattr(rss_toggle_service_module, "set_rss_feed_enabled", lambda _db, feed_id, enabled: False)

    with pytest.raises(RssFeedNotFoundError):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=11, enabled=False)

    db.rollback.assert_called_once()


def test_toggle_rss_company_enabled_raises_when_company_is_missing(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(rss_toggle_service_module, "get_company_by_id", lambda _db, _company_id: None)

    with pytest.raises(RssCompanyNotFoundError, match="RSS company 4 not found"):
        rss_toggle_service_module.toggle_rss_company_enabled(db, company_id=4, enabled=False)


def test_toggle_rss_company_enabled_updates_and_commits(monkeypatch) -> None:
    db = Mock(spec=Session)
    company = SimpleNamespace(id=12, enabled=True)
    monkeypatch.setattr(rss_toggle_service_module, "get_company_by_id", lambda _db, _company_id: company)
    monkeypatch.setattr(rss_toggle_service_module, "set_rss_company_enabled", lambda _db, company_id, enabled: True)

    result = rss_toggle_service_module.toggle_rss_company_enabled(db, company_id=12, enabled=False)

    assert result.company_id == 12
    assert result.enabled is False
    db.commit.assert_called_once()
