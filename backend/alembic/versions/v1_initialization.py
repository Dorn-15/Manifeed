"""squashed initial schema baseline

Revision ID: v1_initialization
Revises:
Create Date: 2026-03-11 00:00:00.000000

"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_initialization"
down_revision = None
branch_labels = None
depends_on = None

_SOURCE_PUBLISHED_AT_FALLBACK_SQL = "TIMESTAMPTZ '1970-01-01 00:00:00+00'"

embedding_item_status_enum = postgresql.ENUM(
    "pending",
    "success",
    "error",
    name="embedding_item_status_enum",
    create_type=False,
)
rss_feed_runtime_status_enum = postgresql.ENUM(
    "pending",
    "success",
    "not_modified",
    "error",
    name="rss_feed_runtime_status_enum",
    create_type=False,
)
rss_scrape_item_status_enum = postgresql.ENUM(
    "pending",
    "success",
    "not_modified",
    "error",
    name="rss_scrape_item_status_enum",
    create_type=False,
)
worker_execution_error_stage_enum = postgresql.ENUM(
    "invalid_payload",
    "worker_loop",
    "fetch_feed",
    "embedding",
    "model_mismatch",
    name="worker_execution_error_stage_enum",
    create_type=False,
)
worker_job_kind_enum = postgresql.ENUM(
    "rss_scrape_check",
    "rss_scrape_ingest",
    "source_embedding",
    name="worker_job_kind_enum",
    create_type=False,
)
worker_job_status_enum = postgresql.ENUM(
    "queued",
    "processing",
    "completed",
    "completed_with_errors",
    "failed",
    name="worker_job_status_enum",
    create_type=False,
)
worker_kind_enum = postgresql.ENUM(
    "rss_scrapper",
    "source_embedding",
    name="worker_kind_enum",
    create_type=False,
)
worker_runtime_kind_enum = postgresql.ENUM(
    "cpu",
    "gpu",
    "npu",
    "unknown",
    name="worker_runtime_kind_enum",
    create_type=False,
)
worker_task_outcome_enum = postgresql.ENUM(
    "success",
    "error",
    name="worker_task_outcome_enum",
    create_type=False,
)
worker_task_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="worker_task_status_enum",
    create_type=False,
)


def upgrade() -> None:
    _create_enum_types()
    _create_catalog_tables()
    _create_source_tables()
    _create_embedding_tables()
    _create_worker_identity_tables()
    _create_worker_tables()
    _create_rss_catalog_sync_state_table()


def downgrade() -> None:
    for table_name in (
        "rss_catalog_sync_state",
        "source_embedding_task_executions",
        "source_embedding_task_items",
        "source_embedding_tasks",
        "rss_scrape_task_executions",
        "rss_scrape_task_items",
        "rss_scrape_tasks",
        "worker_auth_challenges",
        "worker_instances",
        "worker_identities",
        "worker_jobs",
        "rss_source_embedding_projection_states",
        "rss_source_embedding_layouts",
        "rss_source_embeddings",
        "embedding_models",
        "rss_source_feeds",
        "rss_source_contents",
        "rss_sources",
        "rss_feed_runtime",
        "rss_feed_tags",
        "rss_tags",
        "rss_feeds",
        "rss_company",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

    _drop_enum_types()


def _create_enum_types() -> None:
    bind = op.get_bind()
    for enum_type in (
        embedding_item_status_enum,
        rss_feed_runtime_status_enum,
        rss_scrape_item_status_enum,
        worker_execution_error_stage_enum,
        worker_job_kind_enum,
        worker_job_status_enum,
        worker_kind_enum,
        worker_runtime_kind_enum,
        worker_task_outcome_enum,
        worker_task_status_enum,
    ):
        enum_type.create(bind, checkfirst=True)


def _drop_enum_types() -> None:
    bind = op.get_bind()
    for enum_type in (
        worker_task_status_enum,
        worker_task_outcome_enum,
        worker_runtime_kind_enum,
        worker_kind_enum,
        worker_job_status_enum,
        worker_job_kind_enum,
        worker_execution_error_stage_enum,
        rss_scrape_item_status_enum,
        rss_feed_runtime_status_enum,
        embedding_item_status_enum,
    ):
        enum_type.drop(bind, checkfirst=True)


def _create_catalog_tables() -> None:
    op.create_table(
        "rss_company",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("icon_url", sa.String(length=500), nullable=True),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("language", sa.CHAR(length=2), nullable=True),
        sa.Column(
            "fetchprotection",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 2",
            name="ck_rss_company_fetchprotection",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rss_company_name"),
    )
    op.create_index("idx_rss_company_country", "rss_company", ["country"], unique=False)
    op.create_index("idx_rss_company_language", "rss_company", ["language"], unique=False)

    op.create_table(
        "rss_feeds",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "trust_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.5"),
        ),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("fetchprotection_override", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "fetchprotection_override IS NULL OR (fetchprotection_override >= 0 AND fetchprotection_override <= 2)",
            name="ck_rss_feeds_fetchprotection_override",
        ),
        sa.CheckConstraint(
            "trust_score >= 0.0 AND trust_score <= 1.0",
            name="ck_rss_feeds_trust_score",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["rss_company.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
    )
    op.create_index("idx_rss_feeds_company_id", "rss_feeds", ["company_id"], unique=False)
    op.create_index(
        "idx_rss_feeds_enabled",
        "rss_feeds",
        ["enabled"],
        unique=False,
        postgresql_where=sa.text("enabled = true"),
    )

    op.create_table(
        "rss_tags",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rss_tags_name"),
    )

    op.create_table(
        "rss_feed_tags",
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["rss_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feed_id", "tag_id"),
    )
    op.create_index("idx_rss_feed_tags_tag_id", "rss_feed_tags", ["tag_id"], unique=False)

    op.create_table(
        "rss_feed_runtime",
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_status",
            rss_feed_runtime_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::rss_feed_runtime_status_enum"),
        ),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_feed_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consecutive_error_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "consecutive_error_count >= 0",
            name="ck_rss_feed_runtime_consecutive_error_count",
        ),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feed_id"),
    )
    op.create_index(
        "idx_rss_feed_runtime_last_status",
        "rss_feed_runtime",
        ["last_status"],
        unique=False,
    )
    op.create_index(
        "idx_rss_feed_runtime_last_success_at",
        "rss_feed_runtime",
        ["last_success_at"],
        unique=False,
    )


def _create_source_tables() -> None:
    op.create_table(
        "rss_sources",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(_SOURCE_PUBLISHED_AT_FALLBACK_SQL),
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", "published_at", name="uq_rss_sources_url_published_at"),
    )
    op.create_index("idx_rss_sources_published_at", "rss_sources", ["published_at"], unique=False)
    op.create_index("idx_rss_sources_ingested_at", "rss_sources", ["ingested_at"], unique=False)

    op.create_table(
        "rss_source_contents",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "ingested_at"),
        postgresql_partition_by="RANGE (ingested_at)",
    )
    op.create_index(
        "idx_rss_source_contents_ingested_at",
        "rss_source_contents",
        ["ingested_at"],
        unique=False,
    )

    op.create_table(
        "rss_source_feeds",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "feed_id", "ingested_at"),
        postgresql_partition_by="RANGE (ingested_at)",
    )
    op.create_index(
        "idx_rss_source_feeds_source_id_ingested_at",
        "rss_source_feeds",
        ["source_id", "ingested_at"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_feed_id",
        "rss_source_feeds",
        ["feed_id"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_ingested_at",
        "rss_source_feeds",
        ["ingested_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TABLE rss_source_contents_default
        PARTITION OF rss_source_contents DEFAULT
        """
    )
    op.execute(
        """
        CREATE TABLE rss_source_feeds_default
        PARTITION OF rss_source_feeds DEFAULT
        """
    )

    for partition_start in _monthly_partition_starts():
        _create_monthly_partition_pair(partition_start)


def _create_embedding_tables() -> None:
    op.create_table(
        "embedding_models",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_embedding_models_code"),
    )

    op.create_table(
        "rss_source_embeddings",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("embedding_model_id", sa.Integer(), nullable=False),
        sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"],
            ["embedding_models.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "idx_rss_source_embeddings_model_id",
        "rss_source_embeddings",
        ["embedding_model_id"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_embeddings_updated_at",
        "rss_source_embeddings",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "rss_source_embedding_layouts",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("embedding_model_id", sa.Integer(), nullable=False),
        sa.Column("projection_version", sa.String(length=80), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"],
            ["embedding_models.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        "idx_rss_source_embedding_layouts_model_updated",
        "rss_source_embedding_layouts",
        ["embedding_model_id", "embedding_updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_embedding_layouts_projection_version",
        "rss_source_embedding_layouts",
        ["projection_version"],
        unique=False,
    )

    op.create_table(
        "rss_source_embedding_projection_states",
        sa.Column("embedding_model_id", sa.Integer(), nullable=False),
        sa.Column("projection_version", sa.String(length=80), nullable=False),
        sa.Column("projector_kind", sa.String(length=40), nullable=False),
        sa.Column("projector_state", sa.LargeBinary(), nullable=False),
        sa.Column("fitted_sources_count", sa.Integer(), nullable=False),
        sa.Column("last_embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"],
            ["embedding_models.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("embedding_model_id"),
    )
    op.create_index(
        "idx_rss_source_embedding_projection_states_projection_version",
        "rss_source_embedding_projection_states",
        ["projection_version"],
        unique=False,
    )


def _create_worker_identity_tables() -> None:
    op.create_table(
        "worker_identities",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("worker_kind", sa.String(length=40), nullable=False),
        sa.Column("device_id", sa.String(length=100), nullable=False),
        sa.Column("public_key", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=120), nullable=True),
        sa.Column("arch", sa.String(length=120), nullable=True),
        sa.Column("worker_version", sa.String(length=80), nullable=True),
        sa.Column(
            "enrollment_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'enrolled'"),
        ),
        sa.Column("last_enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_auth_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "worker_kind IN ('rss_scrapper', 'source_embedding')",
            name="ck_worker_identities_kind",
        ),
        sa.CheckConstraint(
            "enrollment_status IN ('pending', 'enrolled', 'rejected')",
            name="ck_worker_identities_enrollment_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_kind", "device_id", name="uq_worker_identities_kind_device"),
        sa.UniqueConstraint("fingerprint", name="uq_worker_identities_fingerprint"),
    )
    op.create_index(
        "idx_worker_identities_kind_status",
        "worker_identities",
        ["worker_kind", "enrollment_status"],
        unique=False,
    )

    op.create_table(
        "worker_auth_challenges",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("identity_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("challenge", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "purpose IN ('enroll', 'auth')",
            name="ck_worker_auth_challenges_purpose",
        ),
        sa.ForeignKeyConstraint(["identity_id"], ["worker_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_worker_auth_challenges_identity_expires_at",
        "worker_auth_challenges",
        ["identity_id", "expires_at"],
        unique=False,
    )


def _create_worker_tables() -> None:
    op.create_table(
        "worker_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("job_kind", worker_job_kind_enum, nullable=False),
        sa.Column("requested_by", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            worker_job_status_enum,
            nullable=False,
            server_default=sa.text("'queued'::worker_job_status_enum"),
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tasks_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tasks_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("tasks_total >= 0", name="ck_worker_jobs_tasks_total"),
        sa.CheckConstraint("tasks_processed >= 0", name="ck_worker_jobs_tasks_processed"),
        sa.CheckConstraint("items_total >= 0", name="ck_worker_jobs_items_total"),
        sa.CheckConstraint("items_processed >= 0", name="ck_worker_jobs_items_processed"),
        sa.CheckConstraint("items_success >= 0", name="ck_worker_jobs_items_success"),
        sa.CheckConstraint("items_error >= 0", name="ck_worker_jobs_items_error"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_worker_jobs_requested_at", "worker_jobs", ["requested_at"], unique=False)
    op.create_index("idx_worker_jobs_status", "worker_jobs", ["status"], unique=False)

    op.create_table(
        "worker_instances",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("worker_kind", worker_kind_enum, nullable=False),
        sa.Column("worker_name", sa.String(length=100), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pending_tasks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("identity_id", sa.BigInteger(), nullable=True),
        sa.Column("connection_state", sa.String(length=32), nullable=True),
        sa.Column("current_task_id", sa.BigInteger(), nullable=True),
        sa.Column("current_execution_id", sa.BigInteger(), nullable=True),
        sa.Column("current_task_label", sa.String(length=255), nullable=True),
        sa.Column("current_feed_id", sa.Integer(), nullable=True),
        sa.Column("current_feed_url", sa.String(length=1000), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desired_state", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "pending_tasks >= 0",
            name="ck_worker_instances_pending_tasks",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_kind", "worker_name", name="uq_worker_instances_kind_name"),
    )
    op.create_foreign_key(
        "fk_worker_instances_identity_id",
        "worker_instances",
        "worker_identities",
        ["identity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_worker_instances_last_seen_at",
        "worker_instances",
        ["last_seen_at"],
        unique=False,
    )
    op.create_index(
        "idx_worker_instances_identity_id",
        "worker_instances",
        ["identity_id"],
        unique=False,
    )

    op.create_table(
        "rss_scrape_tasks",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            worker_task_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::worker_task_status_enum"),
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feeds_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("feeds_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("feeds_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("feeds_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_rss_scrape_tasks_attempt_count"),
        sa.CheckConstraint("feeds_total >= 0", name="ck_rss_scrape_tasks_feeds_total"),
        sa.CheckConstraint("feeds_processed >= 0", name="ck_rss_scrape_tasks_feeds_processed"),
        sa.CheckConstraint("feeds_success >= 0", name="ck_rss_scrape_tasks_feeds_success"),
        sa.CheckConstraint("feeds_error >= 0", name="ck_rss_scrape_tasks_feeds_error"),
        sa.ForeignKeyConstraint(["job_id"], ["worker_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "batch_no", name="uq_rss_scrape_tasks_job_batch"),
    )
    op.create_index(
        "idx_rss_scrape_tasks_lookup",
        "rss_scrape_tasks",
        ["status", "claim_expires_at", "id"],
        unique=False,
    )
    op.create_index(
        "idx_rss_scrape_tasks_job_id_status",
        "rss_scrape_tasks",
        ["job_id", "status"],
        unique=False,
    )

    op.create_table(
        "rss_scrape_task_items",
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("item_no", sa.Integer(), nullable=False),
        sa.Column("requested_cursor_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            rss_scrape_item_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::rss_scrape_item_status_enum"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("fetchprotection_used", sa.SmallInteger(), nullable=True),
        sa.Column("new_etag", sa.String(length=255), nullable=True),
        sa.Column("new_last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("item_no >= 1", name="ck_rss_scrape_task_items_item_no"),
        sa.CheckConstraint("sources_count >= 0", name="ck_rss_scrape_task_items_sources_count"),
        sa.ForeignKeyConstraint(["task_id"], ["rss_scrape_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "feed_id"),
        sa.UniqueConstraint("task_id", "item_no", name="uq_rss_scrape_task_items_task_item_no"),
    )
    op.create_index(
        "idx_rss_scrape_task_items_feed_id_status",
        "rss_scrape_task_items",
        ["feed_id", "status"],
        unique=False,
    )

    op.create_table(
        "rss_scrape_task_executions",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("worker_instance_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", worker_task_outcome_enum, nullable=True),
        sa.Column("error_stage", worker_execution_error_stage_enum, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "processed_feeds_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "processed_feeds_count >= 0",
            name="ck_rss_scrape_task_executions_processed_feeds_count",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["rss_scrape_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["worker_instance_id"],
            ["worker_instances.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "attempt_no", name="uq_rss_scrape_task_executions_task_attempt"),
    )
    op.create_index(
        "idx_rss_scrape_task_executions_task_id",
        "rss_scrape_task_executions",
        ["task_id"],
        unique=False,
    )

    op.create_table(
        "source_embedding_tasks",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_model_id", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            worker_task_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::worker_task_status_enum"),
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sources_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sources_success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sources_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_source_embedding_tasks_attempt_count",
        ),
        sa.CheckConstraint("sources_total >= 0", name="ck_source_embedding_tasks_sources_total"),
        sa.CheckConstraint(
            "sources_processed >= 0",
            name="ck_source_embedding_tasks_sources_processed",
        ),
        sa.CheckConstraint(
            "sources_success >= 0",
            name="ck_source_embedding_tasks_sources_success",
        ),
        sa.CheckConstraint("sources_error >= 0", name="ck_source_embedding_tasks_sources_error"),
        sa.ForeignKeyConstraint(["job_id"], ["worker_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"],
            ["embedding_models.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "batch_no", name="uq_source_embedding_tasks_job_batch"),
    )
    op.create_index(
        "idx_source_embedding_tasks_lookup",
        "source_embedding_tasks",
        ["status", "claim_expires_at", "id"],
        unique=False,
    )
    op.create_index(
        "idx_source_embedding_tasks_job_id_status",
        "source_embedding_tasks",
        ["job_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_source_embedding_tasks_model_id_status",
        "source_embedding_tasks",
        ["embedding_model_id", "status"],
        unique=False,
    )

    op.create_table(
        "source_embedding_task_items",
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("item_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            embedding_item_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::embedding_item_status_enum"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("item_no >= 1", name="ck_source_embedding_task_items_item_no"),
        sa.CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions >= 0",
            name="ck_source_embedding_task_items_embedding_dimensions",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["source_embedding_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["rss_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "source_id"),
        sa.UniqueConstraint(
            "task_id",
            "item_no",
            name="uq_source_embedding_task_items_task_item_no",
        ),
    )
    op.create_index(
        "idx_source_embedding_task_items_source_id_status",
        "source_embedding_task_items",
        ["source_id", "status"],
        unique=False,
    )

    op.create_table(
        "source_embedding_task_executions",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("worker_instance_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", worker_task_outcome_enum, nullable=True),
        sa.Column("error_stage", worker_execution_error_stage_enum, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "embeddings_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("processing_seconds", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "embeddings_count >= 0",
            name="ck_source_embedding_task_executions_embeddings_count",
        ),
        sa.CheckConstraint(
            "processing_seconds IS NULL OR processing_seconds >= 0",
            name="ck_source_embedding_task_executions_processing_seconds",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["source_embedding_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["worker_instance_id"],
            ["worker_instances.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "attempt_no",
            name="uq_source_embedding_task_executions_task_attempt",
        ),
    )
    op.create_index(
        "idx_source_embedding_task_executions_task_id",
        "source_embedding_task_executions",
        ["task_id"],
        unique=False,
    )


def _create_rss_catalog_sync_state_table() -> None:
    op.create_table(
        "rss_catalog_sync_state",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("last_applied_revision", sa.String(length=64), nullable=True),
        sa.Column("last_seen_revision", sa.String(length=64), nullable=True),
        sa.Column(
            "last_sync_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "last_sync_status IN ('success', 'failed')",
            name="ck_rss_catalog_sync_state_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _monthly_partition_starts() -> list[datetime]:
    current_month_start = datetime.now(timezone.utc).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    previous_month_end = current_month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    next_month_anchor = current_month_start + timedelta(days=32)
    next_month_start = next_month_anchor.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return [previous_month_start, current_month_start, next_month_start]


def _create_monthly_partition_pair(partition_start: datetime) -> None:
    partition_end = (partition_start + timedelta(days=32)).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    suffix = partition_start.strftime("%Y%m")
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS rss_source_contents_m_{suffix}
            PARTITION OF rss_source_contents
            FOR VALUES FROM (:partition_start) TO (:partition_end)
            """
        ).bindparams(
            partition_start=partition_start,
            partition_end=partition_end,
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS rss_source_feeds_m_{suffix}
            PARTITION OF rss_source_feeds
            FOR VALUES FROM (:partition_start) TO (:partition_end)
            """
        ).bindparams(
            partition_start=partition_start,
            partition_end=partition_end,
        )
    )
