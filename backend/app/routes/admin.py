from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email

from ..models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

login_attempts = defaultdict(list)
MAX_ATTEMPTS = 10
WINDOW_MINUTES = 15


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


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
