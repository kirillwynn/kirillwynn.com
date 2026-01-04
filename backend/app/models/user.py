from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    """
    User model.

    Today:
    - Used for admin authentication (Flask-Login)
    - Will be used as the author of posts

    Future-ready:
    - This model can support multiple authors (not only you) without redesigning Posts.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Unique identity fields
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    name = db.Column(db.String(255))

    # Auth
    password_hash = db.Column(db.String(255), nullable=False)

    # Authorization / roles
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Audit / metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship: one user can author many posts.
    #
    # back_populates="author" links to Post.author relationship.
    # lazy="dynamic" returns a query object instead of loading all posts at once
    # (useful when a user can have many posts).
    posts = db.relationship("Post", back_populates="author", lazy="dynamic")

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
