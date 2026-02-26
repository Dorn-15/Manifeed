from app.domain.idempotency_domain import build_idempotency_key
from app.schemas import WorkerResultSchema


def test_build_idempotency_key_returns_job_id_and_feed_id() -> None:
    payload = WorkerResultSchema(
        job_id="job-123",
        ingest=True,
        feed_id=42,
        feed_url="https://example.com/rss.xml",
        status="success",
        fetchprotection=1,
        sources=[],
    )

    assert build_idempotency_key(payload) == ("job-123", 42)
