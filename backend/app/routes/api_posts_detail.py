# backend/app/routes/api_posts_detail.py
#
# Post detail API for the Secret Room frontend.
# - Cookie-session auth (Flask-Login)
# - Admin-only
# - GET /api/posts/<id> -> returns one post

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Post


api_posts_detail_bp = Blueprint("api_posts_detail", __name__, url_prefix="/api/posts")


def _require_admin() -> bool:
    if not current_user.is_authenticated:
        return False
    return bool(getattr(current_user, "is_admin", False))


@api_posts_detail_bp.get("/<int:post_id>")
@login_required
def get_post(post_id: int):
    if not _require_admin():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"ok": False, "error": "not found"}), 404

    return jsonify(
        {
            "ok": True,
            "item": {
                "id": post.id,
                "title": getattr(post, "title", None),
                "slug": getattr(post, "slug", None),
                "status": getattr(post, "status", None),
                "published_at": post.published_at.isoformat() if getattr(post, "published_at", None) else None,
                "updated_at": post.updated_at.isoformat() if getattr(post, "updated_at", None) else None,
                "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
            },
        }
    )
