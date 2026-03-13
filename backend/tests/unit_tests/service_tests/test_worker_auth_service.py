import base64
from datetime import datetime, timezone
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
import pytest

import app.services.internal.worker_auth_service as worker_auth_service_module
from app.clients.database.worker_auth_db_client import WorkerAuthChallengeRecord, WorkerIdentityRecord
from app.schemas.internal import (
    WorkerAuthVerifyRequestSchema,
    WorkerEnrollRequestSchema,
)


def test_enroll_worker_identity_returns_challenge(monkeypatch) -> None:
    db = Mock()
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("utf-8")

    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_enrollment_tokens",
        lambda: {"rss_scrapper": "enroll-token"},
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_shared_enrollment_token",
        lambda: None,
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "upsert_worker_identity",
        lambda *_args, **_kwargs: WorkerIdentityRecord(
            id=7,
            worker_kind="rss_scrapper",
            device_id="device-1",
            public_key=public_key,
            fingerprint="fingerprint",
            display_name="rss_scrapper:device-1",
            hostname="host-1",
            platform="linux",
            arch="x86_64",
            worker_version="1.0.0",
            enrollment_status="enrolled",
            last_enrolled_at=None,
            last_auth_at=None,
        ),
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_issue_challenge_record",
        lambda _db, *, identity_id, purpose: worker_auth_service_module.WorkerAuthChallengeRead(
            identity_id=identity_id,
            challenge_id=f"{purpose}_challenge",
            challenge="random-challenge",
        ),
    )

    result = worker_auth_service_module.enroll_worker_identity(
        WorkerEnrollRequestSchema(
            worker_type="rss_scrapper",
            device_id="device-1",
            public_key=public_key,
            hostname="host-1",
            platform="linux",
            arch="x86_64",
            worker_version="1.0.0",
            enrollment_token="enroll-token",
        ),
        db,
    )

    assert result.identity_id == 7
    assert result.challenge_id == "enroll_challenge"
    db.commit.assert_called_once()


def test_verify_worker_auth_challenge_returns_signed_token(monkeypatch) -> None:
    db = Mock()
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("utf-8")
    message = b"auth_challenge-1:challenge-value"
    signature = base64.b64encode(private_key.sign(message)).decode("utf-8")

    identity = WorkerIdentityRecord(
        id=11,
        worker_kind="source_embedding",
        device_id="device-2",
        public_key=public_key,
        fingerprint="fingerprint-2",
        display_name="source_embedding:device-2",
        hostname="host-2",
        platform="linux",
        arch="x86_64",
        worker_version="2.0.0",
        enrollment_status="enrolled",
        last_enrolled_at=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
        last_auth_at=None,
    )
    refreshed_identity = WorkerIdentityRecord(
        **{
            **identity.__dict__,
            "last_auth_at": datetime(2026, 3, 10, 10, 5, tzinfo=timezone.utc),
        }
    )

    monkeypatch.setattr(
        worker_auth_service_module,
        "get_worker_identity_by_kind_device_id",
        lambda _db, *, worker_kind, device_id: identity,
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "get_worker_auth_challenge_for_update",
        lambda _db, *, identity_id, challenge_id, purpose: WorkerAuthChallengeRecord(
            id="auth_challenge-1",
            identity_id=identity_id,
            purpose=purpose,
            challenge="challenge-value",
            expires_at=datetime(2030, 3, 10, 11, 0, tzinfo=timezone.utc),
            used_at=None,
        ),
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "get_worker_identity_by_id",
        lambda _db, *, identity_id: refreshed_identity,
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_token_secret",
        lambda: "token-secret",
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_token_ttl_seconds",
        lambda: 3600,
    )

    result = worker_auth_service_module.verify_worker_auth_challenge(
        WorkerAuthVerifyRequestSchema(
            worker_type="source_embedding",
            device_id="device-2",
            challenge_id="auth_challenge-1",
            signature=signature,
        ),
        db,
    )

    decoded = jwt.decode(result.access_token, "token-secret", algorithms=["HS256"])
    assert decoded["sub"] == "11"
    assert decoded["worker_type"] == "source_embedding"
    assert decoded["device_id"] == "device-2"
    assert result.worker_profile.identity_id == 11
    db.commit.assert_called_once()


def test_require_authenticated_worker_context_decodes_valid_token(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_token_secret",
        lambda: "token-secret",
    )
    token = jwt.encode(
        {
            "sub": "11",
            "scope": "worker",
            "worker_type": "source_embedding",
            "device_id": "device-2",
            "fingerprint": "fingerprint-2",
            "exp": 2_000_000_000,
        },
        "token-secret",
        algorithm="HS256",
    )

    worker = worker_auth_service_module.require_authenticated_worker_context(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert worker.identity_id == 11
    assert worker.worker_type == "source_embedding"
    assert worker.device_id == "device-2"


def test_require_authenticated_worker_context_rejects_invalid_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_token_secret",
        lambda: "token-secret",
    )
    token = jwt.encode(
        {
            "sub": "11",
            "scope": "admin",
            "worker_type": "source_embedding",
            "device_id": "device-2",
            "fingerprint": "fingerprint-2",
            "exp": 2_000_000_000,
        },
        "token-secret",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exception_info:
        worker_auth_service_module.require_authenticated_worker_context(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        )

    assert exception_info.value.status_code == 403
