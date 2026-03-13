from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.database.worker_auth_db_client import (
    create_worker_auth_challenge,
    get_worker_auth_challenge_for_update,
    get_worker_identity_by_id,
    get_worker_identity_by_kind_device_id,
    mark_worker_auth_challenge_used,
    mark_worker_identity_authenticated,
    upsert_worker_identity,
)
from app.schemas.internal import (
    WorkerAuthChallengeRead,
    WorkerAuthChallengeRequestSchema,
    WorkerAuthVerifyRequestSchema,
    WorkerEnrollRequestSchema,
    WorkerMeRead,
    WorkerProfileRead,
    WorkerSessionRead,
)

DEFAULT_WORKER_TOKEN_TTL_SECONDS = 3600
DEFAULT_WORKER_CHALLENGE_TTL_SECONDS = 300

_worker_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedWorkerContext:
    identity_id: int
    worker_type: str
    device_id: str
    fingerprint: str


def enroll_worker_identity(
    payload: WorkerEnrollRequestSchema,
    db: Session,
) -> WorkerAuthChallengeRead:
    _validate_enrollment_token(
        worker_type=payload.worker_type,
        enrollment_token=payload.enrollment_token,
    )

    public_key_bytes = _decode_base64(payload.public_key)
    if len(public_key_bytes) != 32:
        raise HTTPException(status_code=422, detail="Invalid worker public key")

    try:
        identity = upsert_worker_identity(
            db,
            worker_kind=payload.worker_type,
            device_id=payload.device_id,
            public_key=payload.public_key,
            fingerprint=hashlib.sha256(public_key_bytes).hexdigest(),
            hostname=payload.hostname,
            platform=payload.platform,
            arch=payload.arch,
            worker_version=payload.worker_version,
            enrollment_status="enrolled",
        )
        challenge = _issue_challenge_record(
            db,
            identity_id=identity.id,
            purpose="enroll",
        )
        db.commit()
    except IntegrityError as exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Worker identity conflict") from exception
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return challenge


def issue_worker_auth_challenge(
    payload: WorkerAuthChallengeRequestSchema,
    db: Session,
) -> WorkerAuthChallengeRead:
    identity = get_worker_identity_by_kind_device_id(
        db,
        worker_kind=payload.worker_type,
        device_id=payload.device_id,
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="Unknown worker identity")
    if identity.enrollment_status != "enrolled":
        raise HTTPException(status_code=403, detail="Worker identity is not enrolled")

    try:
        challenge = _issue_challenge_record(
            db,
            identity_id=identity.id,
            purpose="auth",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return challenge


def verify_worker_auth_challenge(
    payload: WorkerAuthVerifyRequestSchema,
    db: Session,
) -> WorkerSessionRead:
    identity = get_worker_identity_by_kind_device_id(
        db,
        worker_kind=payload.worker_type,
        device_id=payload.device_id,
    )
    if identity is None:
        raise HTTPException(status_code=404, detail="Unknown worker identity")
    if identity.enrollment_status != "enrolled":
        raise HTTPException(status_code=403, detail="Worker identity is not enrolled")

    challenge_purpose = "enroll" if payload.challenge_id.startswith("enroll_") else "auth"
    challenge = get_worker_auth_challenge_for_update(
        db,
        identity_id=identity.id,
        challenge_id=payload.challenge_id,
        purpose=challenge_purpose,
    )
    if challenge is None:
        raise HTTPException(status_code=404, detail="Unknown worker auth challenge")
    if challenge.used_at is not None:
        raise HTTPException(status_code=409, detail="Worker auth challenge already used")
    if challenge.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Worker auth challenge expired")

    try:
        _verify_worker_signature(
            public_key=identity.public_key,
            challenge_id=challenge.id,
            challenge=challenge.challenge,
            signature=payload.signature,
        )
        mark_worker_auth_challenge_used(db, challenge_id=challenge.id)
        mark_worker_identity_authenticated(db, identity_id=identity.id)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_resolve_token_ttl_seconds())
        access_token = _issue_worker_session_token(
            identity_id=identity.id,
            worker_type=identity.worker_kind,
            device_id=identity.device_id,
            fingerprint=identity.fingerprint,
            expires_at=expires_at,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    refreshed_identity = get_worker_identity_by_id(db, identity_id=identity.id)
    if refreshed_identity is None:
        raise HTTPException(status_code=404, detail="Unknown worker identity")
    return WorkerSessionRead(
        access_token=access_token,
        expires_at=expires_at,
        worker_profile=_build_worker_profile_read(refreshed_identity),
    )


def read_current_worker_profile(
    db: Session,
    *,
    worker: AuthenticatedWorkerContext,
) -> WorkerMeRead:
    identity = get_worker_identity_by_id(db, identity_id=worker.identity_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Unknown worker identity")
    return WorkerMeRead(worker_profile=_build_worker_profile_read(identity))


def require_authenticated_worker_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_worker_bearer_scheme),
) -> AuthenticatedWorkerContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing worker bearer token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            _resolve_worker_token_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exception:
        raise HTTPException(status_code=401, detail="Invalid worker bearer token") from exception

    if payload.get("scope") != "worker":
        raise HTTPException(status_code=403, detail="Invalid worker token scope")

    try:
        identity_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exception:
        raise HTTPException(status_code=401, detail="Invalid worker token subject") from exception

    worker_type = str(payload.get("worker_type") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    fingerprint = str(payload.get("fingerprint") or "").strip()
    if not worker_type or not device_id or not fingerprint:
        raise HTTPException(status_code=401, detail="Invalid worker token payload")

    return AuthenticatedWorkerContext(
        identity_id=identity_id,
        worker_type=worker_type,
        device_id=device_id,
        fingerprint=fingerprint,
    )


def _issue_challenge_record(
    db: Session,
    *,
    identity_id: int,
    purpose: str,
) -> WorkerAuthChallengeRead:
    challenge = create_worker_auth_challenge(
        db,
        identity_id=identity_id,
        challenge_id=_build_challenge_id(purpose),
        purpose=purpose,
        challenge=_random_token(),
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=_resolve_worker_challenge_ttl_seconds()),
    )
    return WorkerAuthChallengeRead(
        identity_id=challenge.identity_id,
        challenge_id=challenge.id,
        challenge=challenge.challenge,
    )


def _issue_worker_session_token(
    *,
    identity_id: int,
    worker_type: str,
    device_id: str,
    fingerprint: str,
    expires_at: datetime,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(identity_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "scope": "worker",
            "worker_type": worker_type,
            "device_id": device_id,
            "fingerprint": fingerprint,
        },
        _resolve_worker_token_secret(),
        algorithm="HS256",
    )


def _verify_worker_signature(
    *,
    public_key: str,
    challenge_id: str,
    challenge: str,
    signature: str,
) -> None:
    public_key_bytes = _decode_base64(public_key)
    signature_bytes = _decode_base64(signature)
    if len(public_key_bytes) != 32 or len(signature_bytes) != 64:
        raise HTTPException(status_code=422, detail="Invalid worker signature payload")

    message = f"{challenge_id}:{challenge}".encode("utf-8")
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature_bytes, message)
    except InvalidSignature as exception:
        raise HTTPException(status_code=401, detail="Invalid worker signature") from exception


def _build_worker_profile_read(identity) -> WorkerProfileRead:
    return WorkerProfileRead(
        identity_id=identity.id,
        worker_type=identity.worker_kind,
        device_id=identity.device_id,
        fingerprint=identity.fingerprint,
        display_name=identity.display_name,
        hostname=identity.hostname,
        platform=identity.platform,
        arch=identity.arch,
        worker_version=identity.worker_version,
        enrollment_status=identity.enrollment_status,
        last_enrolled_at=identity.last_enrolled_at,
        last_auth_at=identity.last_auth_at,
    )


def _validate_enrollment_token(*, worker_type: str, enrollment_token: str) -> None:
    expected_token = _resolve_enrollment_tokens().get(worker_type) or _resolve_shared_enrollment_token()
    if expected_token is None or enrollment_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid worker enrollment token")


def _resolve_enrollment_tokens() -> dict[str, str]:
    raw_value = os.getenv("WORKER_ENROLLMENT_TOKENS", "").strip()
    if not raw_value:
        return {}

    tokens: dict[str, str] = {}
    for chunk in raw_value.split(","):
        item = chunk.strip()
        if not item or ":" not in item:
            continue
        worker_type, token = item.split(":", 1)
        resolved_worker_type = worker_type.strip()
        resolved_token = token.strip()
        if resolved_worker_type and resolved_token:
            tokens[resolved_worker_type] = resolved_token
    return tokens


def _resolve_shared_enrollment_token() -> str | None:
    raw_value = os.getenv("WORKER_ENROLLMENT_TOKEN", "").strip()
    if not raw_value:
        return None
    return raw_value


def _resolve_worker_token_secret() -> str:
    return os.getenv("WORKER_TOKEN_SECRET", "manifeed-worker-token-secret")


def _resolve_token_ttl_seconds() -> int:
    raw_ttl = os.getenv("WORKER_TOKEN_TTL_SECONDS", str(DEFAULT_WORKER_TOKEN_TTL_SECONDS))
    try:
        ttl_seconds = int(raw_ttl)
    except ValueError:
        return DEFAULT_WORKER_TOKEN_TTL_SECONDS
    return max(60, ttl_seconds)


def _resolve_worker_challenge_ttl_seconds() -> int:
    raw_ttl = os.getenv("WORKER_CHALLENGE_TTL_SECONDS", str(DEFAULT_WORKER_CHALLENGE_TTL_SECONDS))
    try:
        ttl_seconds = int(raw_ttl)
    except ValueError:
        return DEFAULT_WORKER_CHALLENGE_TTL_SECONDS
    return max(30, ttl_seconds)


def _decode_base64(value: str) -> bytes:
    normalized_value = value.strip()
    padded_value = normalized_value + ("=" * (-len(normalized_value) % 4))
    try:
        return base64.b64decode(padded_value.encode("utf-8"), validate=True)
    except Exception as exception:
        raise HTTPException(status_code=422, detail="Invalid worker base64 payload") from exception


def _build_challenge_id(purpose: str) -> str:
    return f"{purpose}_{uuid4().hex}"


def _random_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
