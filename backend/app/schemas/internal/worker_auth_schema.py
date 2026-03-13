from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.enums import WorkerKind


class WorkerProfileRead(BaseModel):
    identity_id: int = Field(ge=1)
    worker_type: WorkerKind
    device_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=160)
    hostname: str | None = Field(default=None, max_length=255)
    platform: str | None = Field(default=None, max_length=120)
    arch: str | None = Field(default=None, max_length=120)
    worker_version: str | None = Field(default=None, max_length=80)
    enrollment_status: str = Field(min_length=1, max_length=20)
    last_enrolled_at: datetime | None = None
    last_auth_at: datetime | None = None


class WorkerAuthChallengeRead(BaseModel):
    identity_id: int = Field(ge=1)
    challenge_id: str = Field(min_length=1, max_length=64)
    challenge: str = Field(min_length=1, max_length=255)


class WorkerSessionRead(BaseModel):
    access_token: str
    expires_at: datetime
    worker_profile: WorkerProfileRead


class WorkerEnrollRequestSchema(BaseModel):
    worker_type: WorkerKind
    device_id: str = Field(min_length=1, max_length=100)
    public_key: str = Field(min_length=1, max_length=255)
    hostname: str | None = Field(default=None, max_length=255)
    platform: str | None = Field(default=None, max_length=120)
    arch: str | None = Field(default=None, max_length=120)
    worker_version: str | None = Field(default=None, max_length=80)
    enrollment_token: str = Field(min_length=1, max_length=500)


class WorkerAuthChallengeRequestSchema(BaseModel):
    worker_type: WorkerKind
    device_id: str = Field(min_length=1, max_length=100)


class WorkerAuthVerifyRequestSchema(BaseModel):
    worker_type: WorkerKind
    device_id: str = Field(min_length=1, max_length=100)
    challenge_id: str = Field(min_length=1, max_length=64)
    signature: str = Field(min_length=1, max_length=255)


class WorkerMeRead(BaseModel):
    worker_profile: WorkerProfileRead
