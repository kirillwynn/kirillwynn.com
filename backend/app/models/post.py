from datetime import datetime
import re

from ..extensions import db


class Post(db.Model):
    """
    Post model.

    Design notes:
    - Stores sanitized HTML for safe rendering (body_html)
    - Optionally stores source (body_md) for future editor support / revisions
    - Uses 'status' + 'published_at' for feed ordering and drafts

    Multi-author ready:
    - Each post is owned by a User via author_id (FK -> users.id).
      This is the key step that enables "let other people write later"
      without redesigning the table.
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

    # Variant A: store rendered HTML for display, keep optional markdown/source
    body_html = db.Column(db.Text, nullable=False, default="")
    body_md = db.Column(db.Text, nullable=True)

    excerpt = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    tags = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, index=True)

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
