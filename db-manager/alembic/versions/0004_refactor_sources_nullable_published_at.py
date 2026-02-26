"""refactor sources schema with nullable published_at

Revision ID: 0004_sources_nullable_pub_at
Revises: 0003_create_feeds_scraping_table
Create Date: 2026-02-25 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_sources_nullable_pub_at"
down_revision = "0003_create_feeds_scraping_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rss_sources_v2",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('rss_sources_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id", name="rss_sources_v2_pkey"),
        sa.UniqueConstraint(
            "url",
            "published_at",
            name="uq_rss_sources_v2_url_published_at",
        ),
    )
    op.create_index(
        "idx_rss_sources_v2_published_at",
        "rss_sources_v2",
        ["published_at"],
        unique=False,
    )

    op.create_table(
        "rss_source_feeds_v2",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["rss_sources_v2.id"],
            name="fk_rss_source_feeds_v2_source",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["rss_feeds.id"],
            name="fk_rss_source_feeds_v2_feed",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "source_id",
            "feed_id",
            name="rss_source_feeds_v2_pkey",
        ),
    )
    op.create_index(
        "idx_rss_source_feeds_v2_feed_id",
        "rss_source_feeds_v2",
        ["feed_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO rss_sources_v2 (id, title, summary, author, url, published_at, image_url)
        SELECT id, title, summary, author, url, published_at, image_url
        FROM rss_sources
        """
    )
    op.execute(
        """
        INSERT INTO rss_source_feeds_v2 (source_id, feed_id)
        SELECT DISTINCT source_id, feed_id
        FROM rss_source_feeds
        """
    )

    op.execute("ALTER SEQUENCE rss_sources_id_seq OWNED BY NONE")
    op.execute("DROP TABLE IF EXISTS rss_source_feeds CASCADE")
    op.execute("DROP TABLE IF EXISTS rss_sources CASCADE")

    op.rename_table("rss_sources_v2", "rss_sources")
    op.rename_table("rss_source_feeds_v2", "rss_source_feeds")

    op.execute("ALTER TABLE rss_sources RENAME CONSTRAINT rss_sources_v2_pkey TO rss_sources_pkey")
    op.execute(
        "ALTER TABLE rss_sources RENAME CONSTRAINT uq_rss_sources_v2_url_published_at TO uq_rss_sources_url_published_at"
    )
    op.execute("ALTER INDEX idx_rss_sources_v2_published_at RENAME TO idx_rss_sources_published_at")
    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT rss_source_feeds_v2_pkey TO rss_source_feeds_pkey"
    )
    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT fk_rss_source_feeds_v2_source TO fk_rss_source_feeds_source"
    )
    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT fk_rss_source_feeds_v2_feed TO fk_rss_source_feeds_feed"
    )
    op.execute(
        "ALTER INDEX idx_rss_source_feeds_v2_feed_id RENAME TO idx_rss_source_feeds_feed_id"
    )

    op.execute("ALTER SEQUENCE rss_sources_id_seq OWNED BY rss_sources.id")
    op.execute(
        """
        SELECT setval(
            'rss_sources_id_seq',
            COALESCE((SELECT MAX(id) FROM rss_sources), 1),
            (SELECT EXISTS(SELECT 1 FROM rss_sources))
        )
        """
    )


def downgrade() -> None:
    op.execute("ALTER SEQUENCE rss_sources_id_seq OWNED BY NONE")

    op.execute(
        """
        CREATE TABLE rss_sources_v1 (
            id INTEGER NOT NULL DEFAULT nextval('rss_sources_id_seq'),
            title VARCHAR(500) NOT NULL,
            summary TEXT,
            author VARCHAR(255),
            url VARCHAR(1000) NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            image_url VARCHAR(1000),
            CONSTRAINT rss_sources_v1_pkey PRIMARY KEY (id, published_at),
            CONSTRAINT uq_rss_sources_v1_url_published_at UNIQUE (url, published_at)
        ) PARTITION BY RANGE (published_at)
        """
    )
    op.create_index(
        "idx_rss_sources_v1_published_at",
        "rss_sources_v1",
        ["published_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TABLE rss_source_feeds_v1 (
            source_id INTEGER NOT NULL,
            feed_id INTEGER NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT rss_source_feeds_v1_pkey PRIMARY KEY (source_id, feed_id, published_at),
            CONSTRAINT fk_rss_source_feeds_v1_source
                FOREIGN KEY (source_id, published_at)
                REFERENCES rss_sources_v1 (id, published_at)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_rss_source_feeds_v1_feed
                FOREIGN KEY (feed_id)
                REFERENCES rss_feeds (id)
                ON DELETE CASCADE
        ) PARTITION BY RANGE (published_at)
        """
    )
    op.create_index(
        "idx_rss_source_feeds_v1_source_id_published_at",
        "rss_source_feeds_v1",
        ["source_id", "published_at"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_v1_feed_id",
        "rss_source_feeds_v1",
        ["feed_id"],
        unique=False,
    )
    op.create_index(
        "idx_rss_source_feeds_v1_published_at",
        "rss_source_feeds_v1",
        ["published_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rss_sources_v1_default
        PARTITION OF rss_sources_v1 DEFAULT
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rss_source_feeds_v1_default
        PARTITION OF rss_source_feeds_v1 DEFAULT
        """
    )

    op.execute(
        """
        INSERT INTO rss_sources_v1 (id, title, summary, author, url, published_at, image_url)
        SELECT id, title, summary, author, url, COALESCE(published_at, now()), image_url
        FROM rss_sources
        """
    )
    op.execute(
        """
        INSERT INTO rss_source_feeds_v1 (source_id, feed_id, published_at)
        SELECT source_link.source_id, source_link.feed_id, source.published_at
        FROM rss_source_feeds AS source_link
        JOIN rss_sources_v1 AS source
            ON source.id = source_link.source_id
        """
    )

    op.drop_index("idx_rss_source_feeds_feed_id", table_name="rss_source_feeds")
    op.drop_table("rss_source_feeds")
    op.drop_index("idx_rss_sources_published_at", table_name="rss_sources")
    op.drop_table("rss_sources")

    op.rename_table("rss_sources_v1", "rss_sources")
    op.rename_table("rss_source_feeds_v1", "rss_source_feeds")
    op.rename_table("rss_sources_v1_default", "rss_sources_default")
    op.rename_table("rss_source_feeds_v1_default", "rss_source_feeds_default")

    op.execute("ALTER TABLE rss_sources RENAME CONSTRAINT rss_sources_v1_pkey TO rss_sources_pkey")
    op.execute(
        "ALTER TABLE rss_sources RENAME CONSTRAINT uq_rss_sources_v1_url_published_at TO uq_rss_sources_url_published_at"
    )
    op.execute("ALTER INDEX idx_rss_sources_v1_published_at RENAME TO idx_rss_sources_published_at")

    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT rss_source_feeds_v1_pkey TO rss_source_feeds_pkey"
    )
    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT fk_rss_source_feeds_v1_source TO fk_rss_source_feeds_source"
    )
    op.execute(
        "ALTER TABLE rss_source_feeds RENAME CONSTRAINT fk_rss_source_feeds_v1_feed TO fk_rss_source_feeds_feed"
    )
    op.execute(
        "ALTER INDEX idx_rss_source_feeds_v1_source_id_published_at RENAME TO idx_rss_source_feeds_source_id_published_at"
    )
    op.execute(
        "ALTER INDEX idx_rss_source_feeds_v1_feed_id RENAME TO idx_rss_source_feeds_feed_id"
    )
    op.execute(
        "ALTER INDEX idx_rss_source_feeds_v1_published_at RENAME TO idx_rss_source_feeds_published_at"
    )

    op.execute("ALTER SEQUENCE rss_sources_id_seq OWNED BY rss_sources.id")
    op.execute(
        """
        SELECT setval(
            'rss_sources_id_seq',
            COALESCE((SELECT MAX(id) FROM rss_sources), 1),
            (SELECT EXISTS(SELECT 1 FROM rss_sources))
        )
        """
    )
