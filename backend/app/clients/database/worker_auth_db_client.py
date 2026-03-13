from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class WorkerIdentityRecord:
    id: int
    worker_kind: str
    device_id: str
    public_key: str
    fingerprint: str
    display_name: str | None
    hostname: str | None
    platform: str | None
    arch: str | None
    worker_version: str | None
    enrollment_status: str
    last_enrolled_at: datetime | None
    last_auth_at: datetime | None


@dataclass(frozen=True)
class WorkerAuthChallengeRecord:
    id: str
    identity_id: int
    purpose: str
    challenge: str
    expires_at: datetime
    used_at: datetime | None


def upsert_worker_identity(
    db: Session,
    *,
    worker_kind: str,
    device_id: str,
    public_key: str,
    fingerprint: str,
    hostname: str | None,
    platform: str | None,
    arch: str | None,
    worker_version: str | None,
    enrollment_status: str,
) -> WorkerIdentityRecord:
    row = (
        db.execute(
            text(
                """
                INSERT INTO worker_identities (
                    worker_kind,
                    device_id,
                    public_key,
                    fingerprint,
                    display_name,
                    hostname,
                    platform,
                    arch,
                    worker_version,
                    enrollment_status,
                    last_enrolled_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :worker_kind,
                    :device_id,
                    :public_key,
                    :fingerprint,
                    :display_name,
                    :hostname,
                    :platform,
                    :arch,
                    :worker_version,
                    :enrollment_status,
                    now(),
                    now(),
                    now()
                )
                ON CONFLICT (worker_kind, device_id)
                DO UPDATE SET
                    public_key = EXCLUDED.public_key,
                    fingerprint = EXCLUDED.fingerprint,
                    display_name = EXCLUDED.display_name,
                    hostname = EXCLUDED.hostname,
                    platform = EXCLUDED.platform,
                    arch = EXCLUDED.arch,
                    worker_version = EXCLUDED.worker_version,
                    enrollment_status = EXCLUDED.enrollment_status,
                    last_enrolled_at = now(),
                    updated_at = now()
                RETURNING
                    id,
                    worker_kind,
                    device_id,
                    public_key,
                    fingerprint,
                    display_name,
                    hostname,
                    platform,
                    arch,
                    worker_version,
                    enrollment_status,
                    last_enrolled_at,
                    last_auth_at
                """
            ),
            {
                "worker_kind": worker_kind,
                "device_id": device_id,
                "public_key": public_key,
                "fingerprint": fingerprint,
                "display_name": f"{worker_kind}:{device_id}",
                "hostname": hostname,
                "platform": platform,
                "arch": arch,
                "worker_version": worker_version,
                "enrollment_status": enrollment_status,
            },
        )
        .mappings()
        .one()
    )
    return _map_worker_identity(row)


def get_worker_identity_by_kind_device_id(
    db: Session,
    *,
    worker_kind: str,
    device_id: str,
) -> WorkerIdentityRecord | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    id,
                    worker_kind,
                    device_id,
                    public_key,
                    fingerprint,
                    display_name,
                    hostname,
                    platform,
                    arch,
                    worker_version,
                    enrollment_status,
                    last_enrolled_at,
                    last_auth_at
                FROM worker_identities
                WHERE worker_kind = :worker_kind
                    AND device_id = :device_id
                """
            ),
            {
                "worker_kind": worker_kind,
                "device_id": device_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return _map_worker_identity(row)


def get_worker_identity_by_id(
    db: Session,
    *,
    identity_id: int,
) -> WorkerIdentityRecord | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    id,
                    worker_kind,
                    device_id,
                    public_key,
                    fingerprint,
                    display_name,
                    hostname,
                    platform,
                    arch,
                    worker_version,
                    enrollment_status,
                    last_enrolled_at,
                    last_auth_at
                FROM worker_identities
                WHERE id = :identity_id
                """
            ),
            {"identity_id": identity_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return _map_worker_identity(row)


def create_worker_auth_challenge(
    db: Session,
    *,
    identity_id: int,
    challenge_id: str,
    purpose: str,
    challenge: str,
    expires_at: datetime,
) -> WorkerAuthChallengeRecord:
    row = (
        db.execute(
            text(
                """
                INSERT INTO worker_auth_challenges (
                    id,
                    identity_id,
                    purpose,
                    challenge,
                    expires_at,
                    created_at
                ) VALUES (
                    :challenge_id,
                    :identity_id,
                    :purpose,
                    :challenge,
                    :expires_at,
                    now()
                )
                RETURNING
                    id,
                    identity_id,
                    purpose,
                    challenge,
                    expires_at,
                    used_at
                """
            ),
            {
                "challenge_id": challenge_id,
                "identity_id": identity_id,
                "purpose": purpose,
                "challenge": challenge,
                "expires_at": expires_at,
            },
        )
        .mappings()
        .one()
    )
    return _map_worker_auth_challenge(row)


def get_worker_auth_challenge_for_update(
    db: Session,
    *,
    identity_id: int,
    challenge_id: str,
    purpose: str,
) -> WorkerAuthChallengeRecord | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    id,
                    identity_id,
                    purpose,
                    challenge,
                    expires_at,
                    used_at
                FROM worker_auth_challenges
                WHERE id = :challenge_id
                    AND identity_id = :identity_id
                    AND purpose = :purpose
                FOR UPDATE
                """
            ),
            {
                "challenge_id": challenge_id,
                "identity_id": identity_id,
                "purpose": purpose,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return _map_worker_auth_challenge(row)


def mark_worker_auth_challenge_used(
    db: Session,
    *,
    challenge_id: str,
) -> None:
    db.execute(
        text(
            """
            UPDATE worker_auth_challenges
            SET used_at = now()
            WHERE id = :challenge_id
            """
        ),
        {"challenge_id": challenge_id},
    )


def mark_worker_identity_authenticated(
    db: Session,
    *,
    identity_id: int,
) -> None:
    db.execute(
        text(
            """
            UPDATE worker_identities
            SET
                last_auth_at = now(),
                updated_at = now()
            WHERE id = :identity_id
            """
        ),
        {"identity_id": identity_id},
    )


def _map_worker_identity(row) -> WorkerIdentityRecord:
    return WorkerIdentityRecord(
        id=int(row["id"]),
        worker_kind=str(row["worker_kind"]),
        device_id=str(row["device_id"]),
        public_key=str(row["public_key"]),
        fingerprint=str(row["fingerprint"]),
        display_name=(str(row["display_name"]) if row["display_name"] is not None else None),
        hostname=(str(row["hostname"]) if row["hostname"] is not None else None),
        platform=(str(row["platform"]) if row["platform"] is not None else None),
        arch=(str(row["arch"]) if row["arch"] is not None else None),
        worker_version=(str(row["worker_version"]) if row["worker_version"] is not None else None),
        enrollment_status=str(row["enrollment_status"]),
        last_enrolled_at=_normalize_datetime(row["last_enrolled_at"]),
        last_auth_at=_normalize_datetime(row["last_auth_at"]),
    )


def _map_worker_auth_challenge(row) -> WorkerAuthChallengeRecord:
    return WorkerAuthChallengeRecord(
        id=str(row["id"]),
        identity_id=int(row["identity_id"]),
        purpose=str(row["purpose"]),
        challenge=str(row["challenge"]),
        expires_at=_normalize_datetime(row["expires_at"]) or datetime.now(timezone.utc),
        used_at=_normalize_datetime(row["used_at"]),
    )


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
