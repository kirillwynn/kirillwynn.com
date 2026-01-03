from datetime import datetime
import re

from ..extensions import db


class Post(db.Model):
    __tablename__ = "posts"
    __table_args__ = (
        db.Index("ix_posts_status_published_at", "status", "published_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, index=True, nullable=False)
    body_html = db.Column(db.Text, nullable=False, default="")
    body_md = db.Column(db.Text)
    excerpt = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    tags = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, index=True)

    @staticmethod
    def slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "-", text)
        text = text.strip("-")
        return text or "post"

    @classmethod
    def unique_slug(cls, desired_slug: str, post_id: int | None = None) -> str:
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
