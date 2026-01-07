# backend/app/routes/api_posts.py
# Posts API for the Secret Room frontend.
# - Cookie-session auth (Flask-Login)
# - Admin-only
# - Minimal endpoints for v1:
#     GET  /api/posts        -> list posts
#     POST /api/posts        -> create draft post

from __future__ import annotations

from uuid import uuid4

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.extensions import csrf, db
from app.models import Post


api_posts_bp = Blueprint("api_posts", __name__, url_prefix="/api/posts")


def _require_admin():
    if not current_user.is_authenticated:
        return False
    return bool(getattr(current_user, "is_admin", False))


@api_posts_bp.get("")
@api_posts_bp.get("/")
@login_required
def list_posts():
    if not _require_admin():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    posts = (
        Post.query.order_by(Post.updated_at.desc())
        .limit(200)
        .all()
    )

    items = []
    for p in posts:
        items.append(
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "status": p.status,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
        )

    return jsonify({"ok": True, "items": items})


@api_posts_bp.post("")
@api_posts_bp.post("/")
@csrf.exempt
@login_required
def create_post():
    if not _require_admin():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    # Minimal "draft" creation:
    # - title/slug must be non-null
    # - author_id is required
    draft_slug = f"draft-{uuid4().hex[:10]}"

    p = Post(
        author_id=current_user.id,
        title="Untitled",
        slug=draft_slug,
        status="draft",
        body_html="",
        body_md="",
    )

    db.session.add(p)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "post": {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "status": p.status,
            },
        }
    )
    