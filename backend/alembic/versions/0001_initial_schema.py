"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-02-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    rss_feed_status = sa.Enum(
        "valid",
        "invalid",
        "unchecked",
        name="rss_feed_status",
    )

    op.create_table(
        "rss_company",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name", name="uq_rss_company_name"),
    )
    op.create_index("idx_rss_company_name", "rss_company", ["name"])

    op.create_table(
        "rss_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name", name="uq_rss_tags_name"),
    )
    op.create_index("idx_rss_tags_name", "rss_tags", ["name"])

    op.create_table(
        "rss_feeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=50), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "status",
            rss_feed_status,
            nullable=False,
            server_default=sa.text("'unchecked'"),
        ),
        sa.Column(
            "trust_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.5"),
        ),
        sa.Column("language", sa.CHAR(length=2), nullable=True),
        sa.Column("icon_url", sa.String(length=500), nullable=True),
        sa.Column(
            "parsing_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["rss_company.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "trust_score >= 0.0 AND trust_score <= 1.0",
            name="ck_rss_feeds_trust_score",
        ),
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
    )
    op.create_index(
        "idx_rss_feeds_enabled",
        "rss_feeds",
        ["enabled"],
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_index(
        "idx_rss_feeds_status",
        "rss_feeds",
        ["status"],
        postgresql_where=sa.text("status = 'valid'"),
    )
    op.create_index("idx_rss_feeds_company_id", "rss_feeds", ["company_id"])
    op.create_index(
        "idx_rss_feeds_company_id_section",
        "rss_feeds",
        ["company_id", "section"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_rss_feeds_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_rss_feeds_updated_at
        BEFORE UPDATE ON rss_feeds
        FOR EACH ROW
        EXECUTE FUNCTION set_rss_feeds_updated_at();
        """
    )
    op.create_table(
        "rss_feed_tags",
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["rss_feeds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["rss_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feed_id", "tag_id"),
    )
    op.create_index("idx_rss_feed_tags_feed_id", "rss_feed_tags", ["feed_id"])
    op.create_index("idx_rss_feed_tags_tag_id", "rss_feed_tags", ["tag_id"])


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_rss_feeds_updated_at ON rss_feeds")
    op.execute("DROP FUNCTION IF EXISTS set_rss_feeds_updated_at")

    op.drop_index("idx_rss_feed_tags_tag_id", table_name="rss_feed_tags")
    op.drop_index("idx_rss_feed_tags_feed_id", table_name="rss_feed_tags")
    op.drop_table("rss_feed_tags")
    op.drop_index("idx_rss_feeds_company_id_section", table_name="rss_feeds")
    op.drop_index("idx_rss_feeds_company_id", table_name="rss_feeds")
    op.drop_index("idx_rss_feeds_status", table_name="rss_feeds")
    op.drop_index("idx_rss_feeds_enabled", table_name="rss_feeds")
    op.drop_table("rss_feeds")

    op.execute("DROP TYPE IF EXISTS rss_feed_status")

    op.drop_index("idx_rss_tags_name", table_name="rss_tags")
    op.drop_table("rss_tags")

    op.drop_index("idx_rss_company_name", table_name="rss_company")
    op.drop_table("rss_company")
