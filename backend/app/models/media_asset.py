"""
MediaAsset model

This table stores metadata about objects living in S3-compatible storage.
The actual file bytes are NOT in Postgres — only:
- who uploaded it (owner)
- where it is in S3 (bucket + object_key)
- what it is (mime type, size, hashes)
- lifecycle status (pending/ready/deleted)

Design notes:
- We intentionally keep this provider-agnostic: AWS / TWC / MinIO / R2 all work
  as long as they are S3-compatible.
- Many-to-many with Post lets the same asset be referenced from multiple posts
  (e.g. shared images, reused attachments).
"""

from __future__ import annotations

from datetime import datetime

from ..extensions import db


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    # Use BigInteger because asset libraries can grow large over time.
    id = db.Column(db.BigInteger, primary_key=True)

    # Who uploaded/owns the asset (admin today, multi-author tomorrow).
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Where the object is stored in S3.
    bucket = db.Column(db.Text, nullable=False)
    object_key = db.Column(db.Text, nullable=False, unique=True)

    # Original filename for UI display (not used for addressing in storage).
    original_filename = db.Column(db.Text)

    # File metadata
    content_type = db.Column(db.Text, nullable=False)  # e.g. "image/png"
    byte_size = db.Column(db.BigInteger, nullable=False)

    # Optional integrity fields:
    # - sha256 is stable and useful for dedup/integrity checks.
    # - etag can be provider-dependent (multi-part uploads differ).
    sha256 = db.Column(db.String(64))
    etag = db.Column(db.Text)

    # Application-level classification (kept as text for flexibility).
    # Examples: "image", "video", "audio", "file"
    kind = db.Column(db.Text, nullable=False, default="file", index=True)

    # Lifecycle:
    # - pending: object key reserved / upload initiated
    # - ready: upload completed + record committed
    # - deleted: soft delete (optional future cleanup job)
    status = db.Column(db.Text, nullable=False, default="ready", index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships:
    # "owner" backref is defined in User model.
    owner = db.relationship("User", back_populates="media_assets")

    # Posts relationship is defined via the association table in Post model.
    posts = db.relationship(
        "Post",
        secondary="post_media_assets",
        back_populates="media_assets",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MediaAsset id={self.id} key={self.object_key!r} kind={self.kind!r} status={self.status!r}>"
