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
from app.schemas.rss import RssFeedRead


def test_toggle_rss_feed_enabled_raises_when_feed_is_missing(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: None,
    )

    with pytest.raises(RssFeedNotFoundError):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=True)


def test_toggle_rss_feed_enabled_raises_when_company_is_disabled(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="valid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=False,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )

    with pytest.raises(RssFeedToggleForbiddenError):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=False)


def test_toggle_rss_feed_enabled_raises_when_disabling_invalid_feed(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="invalid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )

    with pytest.raises(RssFeedToggleForbiddenError):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=False)


def test_toggle_rss_feed_enabled_updates_feed_and_commits(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="valid",
        trust_score=0.8,
        section="Tech",
        country="en",
        icon_url="leMonde/leMonde.svg",
        company_id=3,
        company_name="Le Monde",
        company_enabled=True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "set_rss_feed_enabled",
        lambda _db, feed_id, enabled: True,
    )

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=False)

    assert feed.enabled is False
    assert result.enabled is False
    assert result.company_enabled is True
    db.commit.assert_called_once()


def test_toggle_rss_feed_enabled_does_not_commit_when_value_unchanged(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="valid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=True)

    assert result.enabled is True
    db.commit.assert_not_called()


def test_toggle_rss_feed_enabled_does_not_raise_when_invalid_status_is_unchanged(
    monkeypatch,
) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=False,
        status="invalid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=False)

    assert result.enabled is False
    db.commit.assert_not_called()


def test_toggle_rss_feed_enabled_does_not_raise_when_company_disabled_and_unchanged(
    monkeypatch,
) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="valid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=False,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )

    result = rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=True)

    assert result.enabled is True
    db.commit.assert_not_called()


def test_toggle_rss_feed_enabled_rolls_back_when_update_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = RssFeedRead(
        id=12,
        url="https://example.com/rss",
        enabled=True,
        status="valid",
        trust_score=0.8,
        company_id=3,
        company_name="Le Monde",
        company_enabled=True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: feed,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "set_rss_feed_enabled",
        lambda _db, feed_id, enabled: False,
    )

    with pytest.raises(RssFeedNotFoundError):
        rss_toggle_service_module.toggle_rss_feed_enabled(db, feed_id=12, enabled=False)

    db.rollback.assert_called_once()


def test_toggle_rss_company_enabled_raises_when_company_is_missing(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_company_by_id",
        lambda _db, _company_id: None,
    )

    with pytest.raises(RssCompanyNotFoundError):
        rss_toggle_service_module.toggle_rss_company_enabled(db, company_id=5, enabled=False)


def test_toggle_rss_company_enabled_updates_company_and_commits(monkeypatch) -> None:
    db = Mock(spec=Session)
    company = SimpleNamespace(id=5, name="The Verge", enabled=True)
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_company_by_id",
        lambda _db, _company_id: company,
    )

    result = rss_toggle_service_module.toggle_rss_company_enabled(db, company_id=5, enabled=False)

    assert company.enabled is False
    assert result.enabled is False
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(company)
