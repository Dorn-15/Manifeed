import pytest

import app.services.internal.worker_gateway_service as worker_gateway_service_module
from app.services.internal.worker_auth_service import AuthenticatedWorkerContext
from app.schemas.internal import (
    EmbeddingTaskCompleteRequestSchema,
    RssWorkerStateRequestSchema,
    WorkerTaskClaimRequestSchema,
)


def _rss_worker() -> AuthenticatedWorkerContext:
    return AuthenticatedWorkerContext(
        identity_id=7,
        worker_type="rss_scrapper",
        device_id="device-rss-1",
        fingerprint="fingerprint-rss",
    )


def _embedding_worker() -> AuthenticatedWorkerContext:
    return AuthenticatedWorkerContext(
        identity_id=8,
        worker_type="source_embedding",
        device_id="device-embedding-1",
        fingerprint="fingerprint-embedding",
    )


def test_claim_rss_tasks_service_validates_client_payload(monkeypatch) -> None:
    def fake_claim_scrape_tasks(*, worker_identity_id, worker_id, count, lease_seconds):
        assert worker_identity_id == 7
        assert worker_id == "device-rss-1"
        assert count == 2
        assert lease_seconds == 450
        return [(1, 2, {"job_id": "job-1"})]

    monkeypatch.setattr(
        worker_gateway_service_module,
        "claim_scrape_tasks",
        fake_claim_scrape_tasks,
    )

    result = worker_gateway_service_module.claim_rss_tasks(
        worker=_rss_worker(),
        payload=WorkerTaskClaimRequestSchema(count=2, lease_seconds=450),
    )

    assert [item.model_dump() for item in result] == [
        {"task_id": 1, "execution_id": 2, "payload": {"job_id": "job-1"}}
    ]


def test_complete_embedding_task_service_validates_command_response(monkeypatch) -> None:
    def fake_complete_source_embedding_task(
        *,
        worker_identity_id,
        worker_id,
        task_id,
        execution_id,
        result_payload,
    ):
        assert worker_identity_id == 8
        assert worker_id == "device-embedding-1"
        assert task_id == 10
        assert execution_id == 20
        assert result_payload == {"sources": []}

    monkeypatch.setattr(
        worker_gateway_service_module,
        "complete_source_embedding_task",
        fake_complete_source_embedding_task,
    )

    result = worker_gateway_service_module.complete_embedding_task(
        worker=_embedding_worker(),
        payload=EmbeddingTaskCompleteRequestSchema(
            task_id=10,
            execution_id=20,
            result_payload={"sources": []},
        ),
    )

    assert result.ok is True


def test_update_rss_state_routes_authenticated_worker(monkeypatch) -> None:
    def fake_update_worker_state(
        *,
        worker_identity_id,
        worker_id,
        active,
        connection_state,
        pending_tasks,
        current_task_id,
        current_execution_id,
        current_task_label,
        current_feed_id,
        current_feed_url,
        last_error,
        desired_state,
    ):
        assert worker_identity_id == 7
        assert worker_id == "device-rss-1"
        assert active is True
        assert connection_state == "processing"
        assert pending_tasks == 1
        assert current_task_id == 100
        assert current_execution_id == 200
        assert current_task_label == "feed 10"
        assert current_feed_id == 10
        assert current_feed_url == "https://example.com/rss.xml"
        assert last_error is None
        assert desired_state == "running"

    monkeypatch.setattr(
        worker_gateway_service_module,
        "update_worker_state",
        fake_update_worker_state,
    )

    result = worker_gateway_service_module.update_rss_state(
        worker=_rss_worker(),
        payload=RssWorkerStateRequestSchema(
            active=True,
            connection_state="processing",
            pending_tasks=1,
            current_task_id=100,
            current_execution_id=200,
            current_task_label="feed 10",
            current_feed_id=10,
            current_feed_url="https://example.com/rss.xml",
            last_error=None,
            desired_state="running",
        ),
    )

    assert result.ok is True


def test_claim_rss_tasks_rejects_wrong_worker_type() -> None:
    with pytest.raises(Exception):
        worker_gateway_service_module.claim_rss_tasks(
            worker=_embedding_worker(),
            payload=WorkerTaskClaimRequestSchema(count=1, lease_seconds=300),
        )
