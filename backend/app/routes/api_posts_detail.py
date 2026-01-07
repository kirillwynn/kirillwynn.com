# backend/app/routes/api_posts_detail.py
#
# Post detail API for the Secret Room frontend.
# - Cookie-session auth (Flask-Login)
# - Admin-only
# - GET   /api/posts/<id>   -> returns one post
# - PATCH /api/posts/<id>   -> updates fields (v1: title + body_md)

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
        "title": getattr(post, "title", None),
        "slug": getattr(post, "slug", None),
        "status": getattr(post, "status", None),
        # ✅ Return body_md so editor can hydrate textarea after refresh
        "body_md": getattr(post, "body_md", None),
        "published_at": post.published_at.isoformat() if getattr(post, "published_at", None) else None,
        "updated_at": post.updated_at.isoformat() if getattr(post, "updated_at", None) else None,
        "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
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
    # v1: allow updating title
    # -------------------------
    if "title" in data:
        title = data.get("title")
        if title is None or not isinstance(title, str):
            return jsonify({"ok": False, "error": "title must be a string"}), 400

        title = title.strip()
        if len(title) == 0:
            return jsonify({"ok": False, "error": "title cannot be empty"}), 400
        if len(title) > 200:
            return jsonify({"ok": False, "error": "title too long (max 200)"}), 400

        post.title = title
        updated_any = True

    # -------------------------
    # v1: allow updating body_md
    # -------------------------
    if "body_md" in data:
        body_md = data.get("body_md")

        # body_md is optional in DB (nullable=True), but for editor it's convenient
        # to treat empty string as "cleared body".
        if body_md is None:
            post.body_md = None
            updated_any = True
        elif not isinstance(body_md, str):
            return jsonify({"ok": False, "error": "body_md must be a string or null"}), 400
        else:
            # allow empty string; optionally cap length to protect DB
            if len(body_md) > 200_000:
                return jsonify({"ok": False, "error": "body_md too long (max 200000)"}), 400
            post.body_md = body_md
            updated_any = True

    # If client sent nothing we understand, return 400
    if not updated_any:
        return jsonify({"ok": False, "error": "no supported fields to update"}), 400

    db.session.commit()
    return jsonify({"ok": True, "item": _post_to_item(post)})
    