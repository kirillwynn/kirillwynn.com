import json
import os

from flask import Blueprint, abort, current_app, render_template, request, redirect
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db, csrf
from ..models import MediaAsset, Post
from ..utils.s3 import presign_get
from ..utils.sanitizer import generate_excerpt

# Public-facing blueprint.
# Contains read-only pages: feed, post detail, static sections, health checks.
main_bp = Blueprint("main", __name__)


@main_bp.route("/feed")
def feed():
    """
    Main feed page.

    Shows only published posts, ordered by:
    1) published_at (newest first, NULLs last)
    2) created_at (fallback for posts that were created earlier)

    The excerpt generator is passed into the template so it can be reused
    consistently for previews.
    """
    posts = (
        Post.query.filter_by(status="published")
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
        .all()
    )
    return render_template("feed.html", posts=posts, excerpt=generate_excerpt)


@main_bp.route("/stash")
def stash():
    """
    Static informational page.

    Currently does not depend on backend state.
    Kept as a normal route (not static HTML) for future extensibility.
    """
    return render_template("stash.html")


@main_bp.route("/stack")
def stack():
    """
    Static informational page describing the tech stack.

    Rendered through Flask to allow future dynamic content
    (e.g. version info, feature flags).
    """
    return render_template("stack.html")


@main_bp.route("/bridge")
def bridge():
    """
    Bridge page with links to external profiles / socials.

    Data source:
    - static/data/socials.json inside the Flask static directory

    This keeps presentation dynamic while avoiding a DB dependency
    for simple link collections.
    """
    json_path = os.path.join(current_app.static_folder, "data", "socials.json")
    with open(json_path, "r", encoding="utf-8") as f:
        socials = json.load(f)["socials"]

    socials_sorted = sorted(socials, key=lambda x: x["order"])
    return render_template("bridge.html", socials=socials_sorted)


@main_bp.route("/webhook", methods=["GET", "POST"])
@csrf.exempt
def webhook():
    """
    Webhook endpoint placeholder.

    - CSRF is explicitly disabled because webhooks are machine-to-machine calls.
    - Currently returns a static response and acts as a connectivity check.

    This endpoint is intentionally minimal and does NOT depend on Telegram
    or any external service at this stage.
    """
    return "Webhook is working! Flask app is running."


@main_bp.route("/db-test")
def db_test():
    """
    Database connectivity test endpoint.

    Executes a trivial SELECT to verify:
    - DB credentials are correct
    - Network connectivity to Postgres exists
    - SQLAlchemy session is operational

    Useful for debugging infrastructure and health checks during deployment.
    """
    try:
        result = db.session.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "result": result}, 200
    except SQLAlchemyError as e:
        current_app.logger.error("DB test failed", exc_info=e)
        return {"error": str(e)}, 500


@main_bp.route("/health")
def health():
    """
    Lightweight health endpoint.

    Used by:
    - uptime monitors
    - load balancers
    - manual sanity checks

    Does NOT touch the database to keep it fast and reliable.
    """
    return {"status": "ok"}, 200


# ---------------------------------------------------------------------
# Stable media URL (recommended approach)
# ---------------------------------------------------------------------
# Why this endpoint exists:
# - We DO NOT store expiring presigned URLs inside post HTML.
# - Posts reference stable URLs like /media/<id>.
# - When a reader opens /media/<id>, the backend generates a short-lived
#   presigned GET URL and issues an HTTP redirect to object storage.
#
# Result:
# - Posts never "rot" because a link expired.
# - Bucket can remain private by default.
# - You can later add access control here (private posts, paid posts, etc.).
@main_bp.route("/media/<int:asset_id>")
def media_redirect(asset_id: int):
    """
    Redirect to a short-lived presigned GET URL for a MediaAsset.

    Access rules today:
    - Public access is allowed for assets with status="ready".
      (If you later need private assets, enforce auth here.)
    """
    # If S3 isn't configured, media feature is effectively disabled.
    if not current_app.config.get("MEDIA_ENABLED", False):
        abort(503, description="Media storage is not configured")

    asset = db.session.get(MediaAsset, asset_id) or abort(404)
    if asset.status != "ready":
        abort(404)

    url = presign_get(
        bucket=asset.bucket,
        key=asset.object_key,
        expires_in=current_app.config["S3_PRESIGN_EXPIRES_IN"],
    )

    # Use a redirect so the browser downloads/streams directly from object storage.
    # (No need to proxy the bytes through Flask.)
    return redirect(url, code=302)


@main_bp.route("/posts/<slug>")
def post_detail(slug: str):
    """
    Post detail page.

    Access rules:
    - Published posts are publicly visible.
    - Draft posts return 404 unless:
        * user is authenticated
        * user is admin
        * ?preview=1 query parameter is present

    This allows safe previewing of drafts without exposing them publicly.
    """
    post = Post.query.filter_by(slug=slug).first_or_404()

    is_preview_allowed = (
        current_user.is_authenticated
        and current_user.is_admin
        and request.args.get("preview") == "1"
    )

    if post.status != "published" and not is_preview_allowed:
        abort(404)

    return render_template("post_detail.html", post=post)
