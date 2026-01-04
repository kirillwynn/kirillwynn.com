from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    """
    User model.

    Today:
    - Used for admin authentication (Flask-Login)
    - Used as the author of posts (Post.author_id -> users.id)
    - Will be used as the owner/uploader of media assets (MediaAsset.owner_id -> users.id)

    Future-ready:
    - Supports multiple authors (not only you) without redesigning Posts.
    - Supports per-user media library (needed for a real editor with uploads).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # -----------------------------------------------------------------
    # Identity fields
    # -----------------------------------------------------------------
    # email is the login identity; keep it unique + indexed for fast lookup.
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    name = db.Column(db.String(255))

    # -----------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------
    # We never store raw passwords — only a secure hash.
    password_hash = db.Column(db.String(255), nullable=False)

    # -----------------------------------------------------------------
    # Authorization / roles
    # -----------------------------------------------------------------
    # For now the site is single-author with an admin panel.
    # Later you can extend this to role-based access control.
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # -----------------------------------------------------------------
    # Audit / metadata
    # -----------------------------------------------------------------
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # -----------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------

    # Relationship: one user can author many posts.
    #
    # back_populates="author" links to Post.author relationship.
    #
    # About lazy="dynamic":
    # - It returns a query object instead of a list (good for large collections).
    # - It also means you can't use selectinload/prefetch as nicely.
    # Since your feed is likely to query posts globally (not via user.posts),
    # keeping dynamic is fine for now and matches your current code style.
    posts = db.relationship("Post", back_populates="author", lazy="dynamic")

    # Relationship: one user can own/upload many media assets.
    #
    # This is important for:
    # - attributing uploads ("who uploaded this file?")
    # - multi-author future (each author has their own media library)
    #
    # We use lazy="selectin" here because most UI screens that list assets
    # will load a batch and benefit from efficient prefetching.
    media_assets = db.relationship(
        "MediaAsset",
        back_populates="owner",
        lazy="selectin",
    )

    # -----------------------------------------------------------------
    # Methods
    # -----------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """
        Flask-Login uses is_active to determine whether an account can log in.
        We always return True for now (no "disabled account" feature yet).
        """
        return True
