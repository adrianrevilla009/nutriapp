"""Create catalog-service tables: products, product_sources, outbox,
ingestion_runs.

CREATE TABLE-only — additive by construction (database-migrations
SKILL.md), does not trigger the destructive-change approval gate.

Adds the `pg_trgm` extension (typo-tolerant search, ADR-0012) and a
generated `tsvector` column + GIN index on `products` for full-text
search, plus a trigram GIN index on `name`/`brand` for fuzzy matching.
`CREATE EXTENSION IF NOT EXISTS pg_trgm` is itself additive/safe but is a
superuser/extension-privilege operation on some managed Postgres setups —
flagged as a migration-time risk in the implementation plan section 7,
not a blocking one; validated here against the local/dev Postgres image
only (a real RDS parameter-group check is an infra-execution-time
concern).

Revision ID: 0001
Revises:
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table(
        "products",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("barcode", sa.String(14), nullable=True, unique=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("nutrient_panel", postgresql.JSONB(), nullable=True),
        sa.Column(
            "dietary_tags", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"
        ),
        sa.Column(
            "allergen_tags", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"
        ),
        sa.Column("package_size", postgresql.JSONB(), nullable=True),
        sa.Column("price", postgresql.JSONB(), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("catalogued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Generated tsvector column combining name + brand + category, GIN
    # indexed for full-text search (ADR-0012). Kept out of the ORM's
    # INSERT/UPDATE column list (models.py declares it read-only).
    op.execute(
        """
        ALTER TABLE products
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(brand, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(category, '')), 'C')
        ) STORED;
        """
    )
    op.execute("CREATE INDEX ix_products_search_vector ON products USING GIN (search_vector);")
    op.execute("CREATE INDEX ix_products_name_trgm ON products USING GIN (name gin_trgm_ops);")
    op.execute("CREATE INDEX ix_products_brand_trgm ON products USING GIN (brand gin_trgm_ops);")

    op.create_table(
        "product_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.product_id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_product_id", sa.String(128), nullable=False),
        sa.Column("raw_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_product_sources_product_id", "product_sources", ["product_id"])
    op.create_index(
        "ix_product_sources_source_product",
        "product_sources",
        ["source", "source_product_id"],
        unique=True,
    )

    op.create_table(
        "outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_product_sources_source_product", table_name="product_sources")
    op.drop_index("ix_product_sources_product_id", table_name="product_sources")
    op.drop_table("product_sources")
    op.execute("DROP INDEX IF EXISTS ix_products_brand_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_products_name_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_products_search_vector;")
    op.execute("ALTER TABLE products DROP COLUMN search_vector;")
    op.drop_table("products")
