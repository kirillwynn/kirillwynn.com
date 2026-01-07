from datetime import datetime
import re

from ..extensions import db

# ---------------------------------------------------------------------
# Association table: posts <-> media_assets (many-to-many)
# ---------------------------------------------------------------------
# Why an association table instead of `post.media_asset_id` FK?
# - One Post can reference many media assets (gallery / multiple images / attachments).
# - The same MediaAsset can be reused across multiple posts (no duplication).
# - We can store per-post usage metadata (role, sort_order) on the link itself.
#
# NOTE:
# - This maps to the DB table we created via Alembic: `post_media_assets`.
# - Even though this is a "Table" (not a Model), SQLAlchemy can still use it
#   as the `secondary=` join table for many-to-many relationships.
post_media_assets = db.Table(
    "post_media_assets",
    # Composite primary key ensures each asset can be linked once per post.
    db.Column(
        "post_id",
        db.Integer,
        db.ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "media_asset_id",
        db.BigInteger,
        db.ForeignKey("media_assets.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    # Optional "usage metadata" (matches the migration schema).
    # - role: how the asset is used inside the post (cover/inline/etc.)
    # - sort_order: stable ordering in galleries
    # - created_at: audit trail for when it was attached to this post
    db.Column("role", db.Text, nullable=True),
    db.Column("sort_order", db.Integer, nullable=True),
    db.Column("created_at", db.DateTime, nullable=False, default=datetime.utcnow),
)


class Post(db.Model):
    """
    Post model.

    Design notes:
    - Stores sanitized HTML for safe rendering (body_html)
    - Stores the rich editor canonical state as TipTap/ProseMirror JSON (body_json)
    - Optionally stores source (body_md) for export/compatibility
    - Uses 'status' + 'published_at' for feed ordering and drafts

    Multi-author ready:
    - Each post is owned by a User via author_id (FK -> users.id).
      This is the key step that enables "let other people write later"
      without redesigning the table.

    Media-ready:
    - Many-to-many to MediaAsset through `post_media_assets`.
      This enables image galleries / attachments / reusable assets.
    """

    __tablename__ = "posts"

    __table_args__ = (
        # Helps feed queries: "published posts ordered by published_at"
        db.Index("ix_posts_status_published_at", "status", "published_at"),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Author reference:
    # - Required (nullable=False) so every post always has an owner/author.
    # - ondelete="RESTRICT" prevents deleting a user who still owns posts
    #   (safer default than cascading deletes for content).
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationship object (Post.author -> User, User.posts -> many posts)
    author = db.relationship("User", back_populates="posts")

    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, index=True, nullable=False)

    # Storage strategy:
    # - body_json: canonical editor state (TipTap/ProseMirror JSON serialized as text)
    # - body_html: sanitized HTML for safe rendering
    # - body_md: optional source/export (kept for compatibility)
    body_json = db.Column(db.Text, nullable=True)
    body_html = db.Column(db.Text, nullable=False, default="")
    body_md = db.Column(db.Text, nullable=True)

    excerpt = db.Column(db.Text)

    # Status design:
    # - draft: not visible publicly
    # - published: visible publicly, ordered by published_at
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)

    # Simple tags v1 (comma-separated). Can be normalized later if needed.
    tags = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    published_at = db.Column(db.DateTime, index=True)

    # -----------------------------------------------------------------
    # Relationships: Media assets attached to this post
    # -----------------------------------------------------------------
    # `secondary="post_media_assets"` references the association table above.
    #
    # `lazy="selectin"` is a good default for many-to-many:
    # - Avoids N+1 queries when loading a list of posts + their assets
    # - Still keeps queries readable and predictable
    media_assets = db.relationship(
        "MediaAsset",
        secondary="post_media_assets",
        back_populates="posts",
        lazy="selectin",
    )

    @staticmethod
    def slugify(text: str) -> str:
        """
        Convert a string to a URL-friendly slug.
        Note: This is intentionally simple and ASCII-only for now.
        """
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        text = text.strip("-")
        return text or "post"

    @classmethod
    def unique_slug(cls, desired_slug: str, post_id: int | None = None) -> str:
        """
        Ensure slug uniqueness by adding -2, -3, ... suffix if needed.
        If post_id is provided (edit mode), exclude this post from uniqueness check.
        """
        base_slug = cls.slugify(desired_slug)
        slug = base_slug
        counter = 2
        while True:
            query = cls.query.filter_by(slug=slug)
            if post_id:
                query = query.filter(cls.id != post_id)
            if not query.first():
                return slug
            slug = f"{base_slug}-{counter}"
            counter += 1
