"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-24 18:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rss_company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("icon_url", sa.String(length=500), nullable=True),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("language", sa.CHAR(length=2), nullable=True),
        sa.Column(
            "fetchprotection",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 3",
            name="ck_rss_company_fetchprotection",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rss_company_name"),
    )
    op.create_index("idx_rss_company_country", "rss_company", ["country"], unique=False)
    op.create_index(
        "idx_rss_company_language",
        "rss_company",
        ["language"],
        unique=False,
    )

    op.create_table(
        "rss_feeds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "trust_score",
            sa.Float(),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column(
            "fetchprotection",
            sa.SmallInteger(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "fetchprotection >= 0 AND fetchprotection <= 3",
            name="ck_rss_feeds_fetchprotection",
        ),
        sa.CheckConstraint(
            "trust_score >= 0.0 AND trust_score <= 1.0",
            name="ck_rss_feeds_trust_score",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["rss_company.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
    )
    op.create_index(
        "idx_rss_feeds_enabled",
        "rss_feeds",
        ["enabled"],
        unique=False,
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_index(
        "idx_rss_feeds_fetchprotection",
        "rss_feeds",
        ["fetchprotection"],
        unique=False,
    )
    op.create_index("idx_rss_feeds_company_id", "rss_feeds", ["company_id"], unique=False)

    op.create_table(
        "rss_tags",
        sa.Column("id", sa.Integer(), nullable=False),
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

    op.execute("CREATE SEQUENCE IF NOT EXISTS rss_sources_id_seq")
    op.execute(
        """
        CREATE TABLE rss_sources (
            id INTEGER NOT NULL DEFAULT nextval('rss_sources_id_seq'),
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            author VARCHAR(255),
            url VARCHAR(1000) NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            image_url VARCHAR(1000),
            CONSTRAINT rss_sources_pkey PRIMARY KEY (id, published_at),
            CONSTRAINT uq_rss_sources_url_published_at UNIQUE (url, published_at)
        ) PARTITION BY RANGE (published_at)
        """
    )
    op.execute("ALTER SEQUENCE rss_sources_id_seq OWNED BY rss_sources.id")
    op.create_index(
        "idx_rss_sources_published_at",
        "rss_sources",
        ["published_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TABLE rss_source_feeds (
            source_id INTEGER NOT NULL,
            feed_id INTEGER NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT rss_source_feeds_pkey PRIMARY KEY (source_id, feed_id, published_at),
            CONSTRAINT fk_rss_source_feeds_source
                FOREIGN KEY (source_id, published_at)
                REFERENCES rss_sources (id, published_at)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_rss_source_feeds_feed
                FOREIGN KEY (feed_id)
                REFERENCES rss_feeds (id)
                ON DELETE CASCADE
        ) PARTITION BY RANGE (published_at)
        """
    )
    op.create_index(
        "idx_rss_source_feeds_source_id_published_at",
        "rss_source_feeds",
        ["source_id", "published_at"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_feed_id",
        "rss_source_feeds",
        ["feed_id"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_published_at",
        "rss_source_feeds",
        ["published_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rss_sources_default
        PARTITION OF rss_sources DEFAULT
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rss_source_feeds_default
        PARTITION OF rss_source_feeds DEFAULT
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rss_source_feeds_default")

    op.drop_index(
        "idx_rss_source_feeds_published_at",
        table_name="rss_source_feeds",
    )
    op.drop_index(
        "idx_rss_source_feeds_feed_id",
        table_name="rss_source_feeds",
    )
    op.drop_index(
        "idx_rss_source_feeds_source_id_published_at",
        table_name="rss_source_feeds",
    )
    op.drop_table("rss_source_feeds")

    op.execute("DROP TABLE IF EXISTS rss_sources_default")

    op.drop_index("idx_rss_sources_published_at", table_name="rss_sources")
    op.drop_table("rss_sources")
    op.execute("DROP SEQUENCE IF EXISTS rss_sources_id_seq")

    op.drop_index("idx_rss_feed_tags_tag_id", table_name="rss_feed_tags")
    op.drop_table("rss_feed_tags")

    op.drop_table("rss_tags")

    op.drop_index("idx_rss_feeds_company_id", table_name="rss_feeds")
    op.drop_index("idx_rss_feeds_fetchprotection", table_name="rss_feeds")
    op.drop_index(
        "idx_rss_feeds_enabled",
        table_name="rss_feeds",
        postgresql_where=sa.text("enabled = true"),
    )
    op.drop_table("rss_feeds")

    op.drop_index("idx_rss_company_language", table_name="rss_company")
    op.drop_index("idx_rss_company_country", table_name="rss_company")
    op.drop_table("rss_company")
