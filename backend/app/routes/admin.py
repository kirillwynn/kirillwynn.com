from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional

from ..extensions import db
from ..models import Post, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

login_attempts = defaultdict(list)
MAX_ATTEMPTS = 10
WINDOW_MINUTES = 15


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class PostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    slug = StringField("Slug")
    tags = StringField("Tags (comma separated)", validators=[Optional()])
    body_md = TextAreaField("Body", validators=[DataRequired()])
    save_draft = SubmitField("Save draft")
    publish = SubmitField("Publish")
    unpublish = SubmitField("Unpublish")


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.index"))

    client_ip = request.remote_addr or "unknown"
    now = datetime.utcnow()

    attempts = login_attempts[client_ip]
    login_attempts[client_ip] = [t for t in attempts if now - t < timedelta(minutes=WINDOW_MINUTES)]

    if len(login_attempts[client_ip]) >= MAX_ATTEMPTS:
        flash("Too many login attempts. Please try again later.", "error")
        return render_template("admin/login.html", form=form), 429

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
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
    logout_user()
    return redirect(url_for("main.feed"))


@admin_bp.route("")
@admin_required
def index():
    return render_template("admin/index.html")


@admin_bp.route("/posts")
@admin_required
def posts_list():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("admin/posts_list.html", posts=posts)


@admin_bp.route("/tiptap-sandbox")
@admin_required
def tiptap_sandbox():
    return render_template("admin/tiptap_sandbox.html")


def _set_post_status_from_form(post: Post, form: PostForm) -> None:
    if form.publish.data:
        post.status = "published"
        post.published_at = datetime.utcnow()
    elif form.unpublish.data:
        post.status = "draft"
        post.published_at = None
    else:
        post.status = "draft"


def _save_post_from_form(post: Post, form: PostForm) -> None:
    post.title = form.title.data.strip()
    desired_slug = form.slug.data.strip() if form.slug.data else post.title
    post.slug = Post.unique_slug(desired_slug, post.id)
    post.body_md = form.body_md.data
    post.tags = form.tags.data.strip() if form.tags.data else None
    _set_post_status_from_form(post, form)
    db.session.add(post)
    db.session.commit()


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@admin_required
def posts_new():
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
    post = db.session.get(Post, post_id) or abort(404)
    form = PostForm(obj=post)
    if form.validate_on_submit():
        _save_post_from_form(post, form)
        flash("Post updated", "success")
        return redirect(url_for("admin.posts_edit", post_id=post.id))
    return render_template("admin/post_form.html", form=form, post=post)


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def posts_delete(post_id: int):
    post = db.session.get(Post, post_id) or abort(404)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted", "success")
    return redirect(url_for("admin.posts_list"))
