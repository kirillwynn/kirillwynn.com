# backend/app/routes/api_posts_detail.py
#
# Posts detail API.
# - GET /api/posts/<id> returns one post (admin only)

from flask import Blueprint, jsonify
from app.extensions import db
from app.models import Post
from app.auth import require_admin

api_posts_detail_bp = Blueprint("api_posts_detail", __name__)


@api_posts_detail_bp.get("/api/posts/<int:post_id>")
@require_admin
def get_post(post_id: int):
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
                "published_at": (
                    post.published_at.isoformat()
                    if getattr(post, "published_at", None)
                    else None
                ),
                "updated_at": (
                    post.updated_at.isoformat()
                    if getattr(post, "updated_at", None)
                    else None
                ),
                "created_at": (
                    post.created_at.isoformat()
                    if getattr(post, "created_at", None)
                    else None
                ),
            },
        }
    )
