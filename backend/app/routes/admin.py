from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Post, User
from ..utils.sanitizer import generate_excerpt, sanitize_html

# Admin blueprint:
# - All admin routes live under /admin/*
# - Protected by Flask-Login + admin_required decorator
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Simple in-memory rate limit for login attempts per IP.
# NOTE: This resets on container restart (good enough for now).
login_attempts = defaultdict(list)
MAX_ATTEMPTS = 10
WINDOW_MINUTES = 15


class LoginForm(FlaskForm):
    """
    Admin login form.

    Uses Flask-WTF, so it automatically includes CSRF protection.
    """
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class PostForm(FlaskForm):
    """
    Post editor form (admin-only).

    body_md is currently used as the editor source field.
    Despite the name, in your current "Variant A" flow we treat it as "raw HTML input"
    coming from the editor, sanitize it, and persist:
      - body_md   : original source (optional, can later become real markdown)
      - body_html : sanitized HTML that is safe to render publicly
    """
    title = StringField("Title", validators=[DataRequired()])
    slug = StringField("Slug")
    tags = StringField("Tags (comma separated)", validators=[Optional()])
    body_md = TextAreaField("Body", validators=[DataRequired()])
    save_draft = SubmitField("Save draft")
    publish = SubmitField("Publish")
    unpublish = SubmitField("Unpublish")


def admin_required(view_func):
    """
    Decorator that enforces:
    1) user is logged in
    2) user has admin privileges

    This is a simple role-gate that keeps the admin panel private.
    """
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Admin login endpoint.

    Security notes:
    - Uses Flask-WTF CSRF token (enabled globally via CSRFProtect).
    - Adds a simple per-IP in-memory rate limit to slow brute force attempts.
    """
    form = LoginForm()

    # If an admin is already authenticated, don't show the login page again.
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.index"))

    client_ip = request.remote_addr or "unknown"
    now = datetime.utcnow()

    # Sliding window: keep only attempts from the last WINDOW_MINUTES.
    attempts = login_attempts[client_ip]
    login_attempts[client_ip] = [t for t in attempts if now - t < timedelta(minutes=WINDOW_MINUTES)]

    if len(login_attempts[client_ip]) >= MAX_ATTEMPTS:
        flash("Too many login attempts. Please try again later.", "error")
        return render_template("admin/login.html", form=form), 429

    if form.validate_on_submit():
        # Normalize email to prevent mismatch due to casing/spaces.
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        # Only admins are allowed into this panel.
        if user and user.is_admin and user.check_password(form.password.data):
            login_attempts.pop(client_ip, None)
            login_user(user)
            return redirect(url_for("admin.index"))

        login_attempts[client_ip].append(now)
        flash("Invalid credentials", "error")

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout")
@admin_required
def logout():
    """Logout endpoint for admins."""
    logout_user()
    return redirect(url_for("main.feed"))


@admin_bp.route("")
@admin_required
def index():
    """Admin dashboard landing page."""
    return render_template("admin/index.html")


@admin_bp.route("/posts")
@admin_required
def posts_list():
    """
    List posts for editing.

    NOTE:
    - Currently shows all posts (draft + published)
    - Later we can add filters (status, author, tags) and pagination
    """
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("admin/posts_list.html", posts=posts)


@admin_bp.route("/tiptap-sandbox")
@admin_required
def tiptap_sandbox():
    """
    Sandbox page for editor experiments (TipTap/Toast UI, etc.).
    Admin-only to avoid exposing experimental scripts publicly.
    """
    return render_template("admin/tiptap_sandbox.html")


def _set_post_status_from_form(post: Post, form: PostForm) -> None:
    """
    Translate form submit intent into Post.status and Post.published_at.

    Rules:
    - "Publish" -> status=published, published_at is set once
    - "Unpublish" -> status=draft, published_at cleared
    - "Save draft" (or any non-publish action) -> status=draft
    """
    if form.publish.data:
        post.status = "published"
        if not post.published_at:
            post.published_at = datetime.utcnow()
    elif form.unpublish.data:
        post.status = "draft"
        post.published_at = None
    else:
        post.status = "draft"


def _save_post_from_form(post: Post, form: PostForm) -> None:
    """
    Persist changes from PostForm into a Post model.

    Multi-author readiness:
    - Posts MUST have an author_id (FK -> users.id).
    - For new posts, we bind the author to the currently authenticated admin.
      This avoids NOT NULL constraint violations after introducing Post.author_id.

    Content pipeline (Variant A):
    - Input from editor -> raw_html (stored in body_md as source)
    - raw_html -> sanitize_html() -> body_html (safe public rendering)
    - excerpt auto-generated once if not already set
    """
    # --- NEW: ensure author is set for new posts ---
    # If post is new (no author_id yet), set it to current admin user.
    # This is required after adding author_id NOT NULL in the DB.
    if not getattr(post, "author_id", None):
        post.author_id = current_user.id
    # ---------------------------------------------

    post.title = form.title.data.strip()
    desired_slug = form.slug.data.strip() if form.slug.data else post.title

    # Enforce slug uniqueness on every save to avoid collisions.
    post.slug = Post.unique_slug(desired_slug, post.id)

    raw_html = form.body_md.data or ""

    # Variant A: store source (currently raw HTML) and sanitized HTML for display.
    post.body_md = raw_html
    post.body_html = sanitize_html(raw_html)

    # Generate excerpt once (you can later regenerate on every save if desired).
    if not post.excerpt:
        post.excerpt = generate_excerpt(post.body_html)

    post.tags = form.tags.data.strip() if form.tags.data else None
    _set_post_status_from_form(post, form)

    db.session.add(post)
    db.session.commit()


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@admin_required
def posts_new():
    """
    Create a new post.

    On success:
    - Saves the post
    - Redirects to the edit page (useful if you want to continue editing)
    """
    form = PostForm()
    if form.validate_on_submit():
        post = Post()
        _save_post_from_form(post, form)
        flash("Post created", "success")
        return redirect(url_for("admin.posts_edit", post_id=post.id))
    return render_template("admin/post_form.html", form=form, post=None)


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def posts_edit(post_id: int):
    """
    Edit an existing post.
    """
    post = db.session.get(Post, post_id) or abort(404)
    form = PostForm(obj=post)

    # On GET: prefill the editor field.
    # Prefer stored source (body_md). Fall back to rendered HTML if needed.
    if request.method == "GET":
        form.body_md.data = post.body_md or post.body_html

    if form.validate_on_submit():
        _save_post_from_form(post, form)
        flash("Post updated", "success")
        return redirect(url_for("admin.posts_edit", post_id=post.id))

    return render_template("admin/post_form.html", form=form, post=post)


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def posts_delete(post_id: int):
    """
    Delete a post.

    NOTE: If you later want "soft delete" (recoverable), we can add deleted_at instead.
    """
    post = db.session.get(Post, post_id) or abort(404)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted", "success")
    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/db-info")
@admin_required
def db_info():
    """
    Small diagnostic endpoint for DB connectivity + Alembic version.
    Admin-only and returns JSON.

    Security:
    - Masks password in the DB URI
    - Helpful for confirming migrations in production
    """
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")

    masked_uri = uri
    try:
        masked_uri = str(make_url(uri).set(password="***"))
    except Exception:  # pragma: no cover - defensive masking
        masked_uri = "<unparsable URI>"

    revision = None
    db_meta: dict[str, str | None] = {
        "database_uri": masked_uri,
        "current_database": None,
        "current_user": None,
    }
    error = None

    try:
        db_meta["current_database"] = db.session.execute(text("SELECT current_database()")).scalar()
        db_meta["current_user"] = db.session.execute(text("SELECT current_user")).scalar()
        revision = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except SQLAlchemyError as exc:  # pragma: no cover - debug endpoint
        current_app.logger.warning("Could not read DB diagnostics", exc_info=exc)
        error = str(exc)

    return jsonify(
        {
            "database": db_meta,
            "alembic_version": revision,
            "error": error,
        }
    )
