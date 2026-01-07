# backend/app/routes/api_posts_detail.py
#
# Post detail API for the Secret Room frontend.
# - Cookie-session auth (Flask-Login)
# - Admin-only
# - GET   /api/posts/<id>  -> returns one post
# - PATCH /api/posts/<id>  -> updates fields (v2: title + body)

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Post


api_posts_detail_bp = Blueprint("api_posts_detail", __name__, url_prefix="/api/posts")


def _require_admin() -> bool:
    if not current_user.is_authenticated:
        return False
    return bool(getattr(current_user, "is_admin", False))


def _post_to_item(post: Post):
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "status": post.status,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        # NOTE: body fields intentionally NOT returned yet
        # they will be added when the editor is wired fully
    }


@api_posts_detail_bp.get("/<int:post_id>")
@login_required
def get_post(post_id: int):
    if not _require_admin():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"ok": False, "error": "not found"}), 404

    return jsonify({"ok": True, "item": _post_to_item(post)})


@api_posts_detail_bp.patch("/<int:post_id>")
@login_required
def patch_post(post_id: int):
    if not _require_admin():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"ok": False, "error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    updated_any = False

    # -------------------------
    # Update title (v1)
    # -------------------------
    if "title" in data:
        title = data.get("title")

        if not isinstance(title, str):
            return jsonify({"ok": False, "error": "title must be a string"}), 400

        title = title.strip()
        if not title:
            return jsonify({"ok": False, "error": "title cannot be empty"}), 400

        if len(title) > 200:
            return jsonify({"ok": False, "error": "title too long (max 200)"}), 400

        post.title = title
        updated_any = True

    # -------------------------
    # Update body (v2: textarea)
    # -------------------------
    if "body" in data:
        body = data.get("body")

        if not isinstance(body, str):
            return jsonify({"ok": False, "error": "body must be a string"}), 400

        # Source of truth (markdown / textarea for now)
        post.body_md = body

        # TEMP v2:
        # Until we introduce markdown / editor rendering,
        # mirror source into HTML.
        post.body_html = body

        updated_any = True

    # -------------------------
    # Nothing to update
    # -------------------------
    if not updated_any:
        return jsonify(
            {"ok": False, "error": "no supported fields to update"},
        ), 400

    db.session.commit()
    return jsonify({"ok": True, "item": _post_to_item(post)})
    