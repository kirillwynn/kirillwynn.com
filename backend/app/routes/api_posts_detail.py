# backend/app/routes/api_posts_detail.py
#
# Post detail API for the Secret Room frontend.
# - Cookie-session auth (Flask-Login)
# - Admin-only
# - GET   /api/posts/<id>  -> returns one post
# - PATCH /api/posts/<id>  -> updates fields (v2: title + body_json + legacy body_md)

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Post


api_posts_detail_bp = Blueprint("api_posts_detail", __name__, url_prefix="/api/posts")


def _require_admin() -> bool:
    if not current_user.is_authenticated:
        return False
    return bool(getattr(current_user, "is_admin", False))


def _post_to_item(post: Post) -> dict[str, Any]:
    body_json_value = getattr(post, "body_json", None)

    # Normalize body_json to a JSON object for the client.
    # We store it as TEXT in DB, so we parse it here.
    body_json_parsed = None
    if isinstance(body_json_value, str) and body_json_value.strip():
        try:
            body_json_parsed = json.loads(body_json_value)
        except Exception:
            # If DB contains invalid JSON, do not crash the API.
            body_json_parsed = None

    return {
        "id": post.id,
        "title": getattr(post, "title", None),
        "slug": getattr(post, "slug", None),
        "status": getattr(post, "status", None),
        "published_at": post.published_at.isoformat() if getattr(post, "published_at", None) else None,
        "updated_at": post.updated_at.isoformat() if getattr(post, "updated_at", None) else None,
        "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
        # v2 canon: authoring format
        "body_json": body_json_parsed,
        # legacy/compat (still returned for now)
        "body_md": getattr(post, "body_md", None),
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

    changed = False

    # v1/v2: title
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
        changed = True

    # v2 canon: body_json
    # Accept either:
    # - object/array (preferred): we will json.dumps() to store in TEXT
    # - string: must be valid JSON string
    if "body_json" in data:
        body_json = data.get("body_json")

        if body_json is None:
            # Allow clearing
            post.body_json = None
            changed = True
        elif isinstance(body_json, str):
            # Client might send a JSON string
            try:
                json.loads(body_json)  # validate
            except Exception:
                return jsonify({"ok": False, "error": "body_json must be valid JSON"}), 400
            post.body_json = body_json
            changed = True
        else:
            # Object/array -> stringify
            try:
                post.body_json = json.dumps(body_json, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                return jsonify({"ok": False, "error": "body_json must be JSON-serializable"}), 400
            changed = True

    # legacy: body_md (keep for compatibility until we fully migrate)
    if "body_md" in data:
        body_md = data.get("body_md")
        if body_md is None:
            post.body_md = None
            changed = True
        elif not isinstance(body_md, str):
            return jsonify({"ok": False, "error": "body_md must be a string"}), 400
        else:
            post.body_md = body_md
            changed = True

    if not changed:
        return jsonify({"ok": False, "error": "no supported fields to update"}), 400

    db.session.commit()
    return jsonify({"ok": True, "item": _post_to_item(post)})
