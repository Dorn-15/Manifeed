import importlib

import app.services.internal.worker_auth_service as worker_auth_service_module
from app.schemas.internal import WorkerAuthChallengeRead, WorkerSessionRead

internal_workers_router_module = importlib.import_module("app.routers.internal_workers_router")


def test_enroll_worker_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    expected = WorkerAuthChallengeRead(
        identity_id=7,
        challenge_id="enroll_challenge",
        challenge="challenge-value",
    )

    def fake_enroll_worker_identity(payload, db):
        assert db is mock_db_session
        assert payload.worker_type == "rss_scrapper"
        assert payload.device_id == "device-1"
        assert payload.enrollment_token == "enroll-token"
        return expected

    monkeypatch.setattr(
        internal_workers_router_module,
        "enroll_worker_identity",
        fake_enroll_worker_identity,
    )

    response = client.post(
        "/internal/workers/enroll",
        json={
            "worker_type": "rss_scrapper",
            "device_id": "device-1",
            "public_key": "public-key",
            "hostname": "host-1",
            "platform": "linux",
            "arch": "x86_64",
            "worker_version": "1.0.0",
            "enrollment_token": "enroll-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_verify_worker_auth_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    expected = WorkerSessionRead(
        access_token="token-value",
        expires_at="2026-03-10T20:00:00Z",
        worker_profile={
            "identity_id": 7,
            "worker_type": "rss_scrapper",
            "device_id": "device-1",
            "fingerprint": "fingerprint",
            "display_name": "rss_scrapper:device-1",
            "hostname": "host-1",
            "platform": "linux",
            "arch": "x86_64",
            "worker_version": "1.0.0",
            "enrollment_status": "enrolled",
            "last_enrolled_at": "2026-03-10T19:55:00Z",
            "last_auth_at": "2026-03-10T20:00:00Z",
        },
    )

    def fake_verify_worker_auth_challenge(payload, db):
        assert db is mock_db_session
        assert payload.challenge_id == "auth_challenge"
        assert payload.signature == "signature-value"
        return expected

    monkeypatch.setattr(
        internal_workers_router_module,
        "verify_worker_auth_challenge",
        fake_verify_worker_auth_challenge,
    )

    response = client.post(
        "/internal/workers/auth/verify",
        json={
            "worker_type": "rss_scrapper",
            "device_id": "device-1",
            "challenge_id": "auth_challenge",
            "signature": "signature-value",
        },
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_claim_rss_tasks_route_uses_authenticated_worker_context(client, monkeypatch) -> None:
    expected_payload = [
        {
            "task_id": 11,
            "execution_id": 21,
            "payload": {
                "job_id": "job-1",
                "feeds": [],
            },
        }
    ]

    def fake_claim_rss_tasks(*, worker, payload):
        assert worker.identity_id == 7
        assert worker.worker_type == "rss_scrapper"
        assert worker.device_id == "device-1"
        assert payload.count == 2
        assert payload.lease_seconds == 600
        return expected_payload

    monkeypatch.setattr(
        internal_workers_router_module,
        "claim_rss_tasks",
        fake_claim_rss_tasks,
    )
    app = importlib.import_module("main").app
    app.dependency_overrides[worker_auth_service_module.require_authenticated_worker_context] = (
        lambda: worker_auth_service_module.AuthenticatedWorkerContext(
            identity_id=7,
            worker_type="rss_scrapper",
            device_id="device-1",
            fingerprint="fingerprint",
        )
    )

    response = client.post(
        "/internal/workers/rss/claim",
        json={"count": 2, "lease_seconds": 600},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == expected_payload


def test_update_rss_state_route_uses_authenticated_worker_context(client, monkeypatch) -> None:
    expected_payload = {"ok": True}

    def fake_update_rss_state(*, worker, payload):
        assert worker.worker_type == "rss_scrapper"
        assert worker.device_id == "device-1"
        assert payload.connection_state == "processing"
        assert payload.current_task_id == 44
        assert payload.current_feed_url == "https://example.com/rss.xml"
        return expected_payload

    monkeypatch.setattr(
        internal_workers_router_module,
        "update_rss_state",
        fake_update_rss_state,
    )
    app = importlib.import_module("main").app
    app.dependency_overrides[worker_auth_service_module.require_authenticated_worker_context] = (
        lambda: worker_auth_service_module.AuthenticatedWorkerContext(
            identity_id=7,
            worker_type="rss_scrapper",
            device_id="device-1",
            fingerprint="fingerprint",
        )
    )

    response = client.post(
        "/internal/workers/rss/state",
        json={
            "active": True,
            "connection_state": "processing",
            "pending_tasks": 1,
            "current_task_id": 44,
            "current_execution_id": 55,
            "current_task_label": "feed 10 - https://example.com/rss.xml",
            "current_feed_id": 10,
            "current_feed_url": "https://example.com/rss.xml",
            "last_error": None,
            "desired_state": "running",
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == expected_payload


def test_read_workers_overview_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    expected_payload = {
        "generated_at": "2026-02-27T15:00:00Z",
        "connected_idle_threshold_ms": 300000,
        "active_idle_threshold_ms": 30000,
        "items": [
            {
                "worker_type": "rss_scrapper",
                "queue_name": "rss_scrape_requests",
                "queue_length": 12,
                "queued_tasks": 11,
                "processing_tasks": 1,
                "worker_count": 1,
                "connected": True,
                "active": True,
                "workers": [
                    {
                        "name": "device-1",
                        "processing_tasks": 1,
                        "idle_ms": 100,
                        "connected": True,
                        "active": True,
                        "connection_state": "processing",
                        "desired_state": "running",
                        "current_task_id": 44,
                        "current_execution_id": 55,
                        "current_task_label": "feed 10 - https://example.com/rss.xml",
                        "current_feed_id": 10,
                        "current_feed_url": "https://example.com/rss.xml",
                        "last_error": None,
                    }
                ],
            }
        ],
    }

    def fake_get_workers_overview(db):
        assert db is mock_db_session
        return expected_payload

    monkeypatch.setattr(
        internal_workers_router_module,
        "get_workers_overview",
        fake_get_workers_overview,
    )

    response = client.get("/internal/workers/overview")

    assert response.status_code == 200
    assert response.json() == expected_payload


def test_read_queues_overview_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    expected_payload = {
        "generated_at": "2026-02-27T15:00:00Z",
        "connected_idle_threshold_ms": 300000,
        "active_idle_threshold_ms": 30000,
        "stuck_pending_threshold_ms": 120000,
        "queue_backend_available": True,
        "queue_backend_error": None,
        "blocked_queues": 1,
        "items": [
            {
                "queue_name": "rss_scrape_requests",
                "purpose": "Scrape jobs produced by backend, consumed by RSS scrapper worker",
                "worker_type": "rss_scrapper",
                "queue_exists": True,
                "queue_length": 12,
                "queued_tasks": 7,
                "processing_tasks": 5,
                "last_task_id": "12",
                "connected_workers": 1,
                "active_workers": 0,
                "blocked": True,
                "blocked_reasons": ["Processing tasks but no active worker"],
                "error": None,
                "workers": [
                    {
                        "name": "worker_rss_scrapper_1",
                        "processing_tasks": 5,
                        "idle_ms": 240000,
                        "connected": True,
                        "active": False,
                    }
                ],
                "leased_tasks": [],
            }
        ],
    }

    def fake_get_queues_overview(db):
        assert db is mock_db_session
        return expected_payload

    monkeypatch.setattr(
        internal_workers_router_module,
        "get_queues_overview",
        fake_get_queues_overview,
    )

    response = client.get("/internal/workers/queues/overview")

    assert response.status_code == 200
    assert response.json() == expected_payload


def test_purge_task_queue_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    expected_payload = {
        "queue_name": "rss_scrape_requests",
        "deleted": True,
        "purged_at": "2026-02-27T16:00:00Z",
    }

    def fake_purge_task_queue(db, queue_name):
        assert db is mock_db_session
        assert queue_name == "rss_scrape_requests"
        return expected_payload

    monkeypatch.setattr(
        internal_workers_router_module,
        "purge_task_queue",
        fake_purge_task_queue,
    )

    response = client.post("/internal/workers/queues/rss_scrape_requests/purge")

    assert response.status_code == 200
    assert response.json() == expected_payload
