"""Add media_assets and post_media_assets tables (S3-backed media library).

Revision ID: 202601042200
Revises: 202601041930
Create Date: 2026-01-04 22:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "202601042200"
down_revision = "202601041930"
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------------------
    # media_assets
    # ---------------------------------------------------------------------
    # Stores metadata about objects stored in S3-compatible object storage.
    # The actual bytes live in S3; this table is the system of record for:
    # - who uploaded it (owner_id)
    # - where it is in S3 (bucket, object_key)
    # - what it is (content_type, byte_size, hashes)
    # - lifecycle status (pending/ready/deleted)
    op.create_table(
        "media_assets",
        sa.Column("id", sa.BigInteger(), primary_key=True),

        sa.Column("owner_id", sa.Integer(), nullable=False),

        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),

        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),

        # Optional integrity fields:
        # - sha256: useful for dedup/integrity verification
        # - etag: sometimes matches md5 for single-part uploads (provider-dependent)
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),

        # Kind is an app-level classification (not enforced by DB enum for flexibility).
        # Examples: image, video, audio, file
        sa.Column("kind", sa.Text(), nullable=False, server_default="file"),

        # Status allows safe lifecycle management and later garbage collection.
        # Examples: pending (uploaded but not verified), ready, deleted
        sa.Column("status", sa.Text(), nullable=False, server_default="ready"),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),

        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"],
            name="fk_media_assets_owner_id_users",
            ondelete="RESTRICT",
        ),
    )

    # Uniqueness: object_key should uniquely identify an object in your bucket naming scheme.
    # (If you plan to use multiple buckets in the future, you could make (bucket, object_key) unique instead.)
    op.create_unique_constraint("uq_media_assets_object_key", "media_assets", ["object_key"])

    # Indexes for common queries
    op.create_index("ix_media_assets_owner_id", "media_assets", ["owner_id"])
    op.create_index("ix_media_assets_kind", "media_assets", ["kind"])
    op.create_index("ix_media_assets_status", "media_assets", ["status"])

    # ---------------------------------------------------------------------
    # post_media_assets (join table)
    # ---------------------------------------------------------------------
    # Many-to-many link:
    # - One Post can reference many MediaAssets
    # - One MediaAsset can be reused in many Posts
    op.create_table(
        "post_media_assets",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("media_asset_id", sa.BigInteger(), nullable=False),

        # Optional fields that help build richer editors / galleries later:
        sa.Column("role", sa.Text(), nullable=True),          # e.g. "cover", "inline"
        sa.Column("sort_order", sa.Integer(), nullable=True), # ordering in galleries
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),

        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"],
            name="fk_post_media_assets_post_id_posts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"], ["media_assets.id"],
            name="fk_post_media_assets_media_asset_id_media_assets",
            ondelete="RESTRICT",
        ),

        sa.PrimaryKeyConstraint("post_id", "media_asset_id", name="pk_post_media_assets"),
    )

    op.create_index("ix_post_media_assets_media_asset_id", "post_media_assets", ["media_asset_id"])


def downgrade():
    # Reverse order: drop join table first, then assets table.
    op.drop_index("ix_post_media_assets_media_asset_id", table_name="post_media_assets")
    op.drop_table("post_media_assets")

    op.drop_index("ix_media_assets_status", table_name="media_assets")
    op.drop_index("ix_media_assets_kind", table_name="media_assets")
    op.drop_index("ix_media_assets_owner_id", table_name="media_assets")
    op.drop_constraint("uq_media_assets_object_key", "media_assets", type_="unique")
    op.drop_table("media_assets")
