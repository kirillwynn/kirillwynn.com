import os
import click

from flask import Flask, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, migrate
from .models import User
from .routes.main import main_bp
from .routes.admin import admin_bp
from .routes.api_auth import api_auth_bp
from .routes.api import api_bp
from .routes.api_posts import api_posts_bp
from .routes.api_posts_detail import api_posts_detail_bp


def create_app():
    """
    Flask application factory.

    High-level responsibilities:
    - Create the Flask app object (with templates + static folder).
    - Load configuration (fail-fast via Config if required env vars are missing).
    - Initialize extensions (SQLAlchemy, Migrate, CSRF, LoginManager).
    - Register blueprints (public site + admin panel).
    - Define a small root redirect and CLI utility commands.
    - Apply reverse-proxy middleware so Flask understands HTTPS/real client IP
      when running behind Nginx (X-Forwarded-* headers).
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Load configuration from app.config (Config validates required env vars and fails fast).
    app.config.from_object(Config)

    # Reverse-proxy support:
    # Nginx forwards requests to this app over HTTP inside Docker network, but the
    # original client connection is HTTPS. ProxyFix makes Flask treat the request
    # as secure and uses the forwarded host/IP for redirects, URL generation, cookies, etc.
    #
    # x_for=1   -> trust one proxy hop for X-Forwarded-For
    # x_proto=1 -> trust one proxy hop for X-Forwarded-Proto
    # x_host=1  -> trust one proxy hop for X-Forwarded-Host
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize Flask extensions.
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    login_manager.session_protection = "strong"

    # Flask-Login callback: how to load a user object from the session user_id.
    @login_manager.user_loader
    def load_user(user_id):
        # user_id is stored in the session as a string; convert to int for primary key lookup.
        return db.session.get(User, int(user_id))

    # Register site blueprints.
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # API blueprints.
    # - api_auth_bp: /api/auth/login, /api/auth/logout, /api/auth/me
    # - api_bp: misc API endpoints (e.g. /api/health proxy wiring / helper endpoints)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_posts_bp)
    app.register_blueprint(api_posts_detail_bp)

    # Redirect the site root "/" to the feed route (the main entry point).
    @app.route("/")
    def root_redirect():
        return redirect(url_for("main.feed"))

    # CLI command: create/update an admin user from environment variables.
    @app.cli.command("create-admin")
    def create_admin_command():
        """Create or update the admin user from environment variables."""
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")
        name = os.getenv("ADMIN_NAME")

        if not email or not password:
            raise click.ClickException("ADMIN_EMAIL and ADMIN_PASSWORD must be set in the environment.")

        email = email.lower().strip()

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            user.is_admin = True
            if name:
                user.name = name
            action = "updated"
        else:
            user = User(email=email, name=name, is_admin=True)
            user.set_password(password)
            db.session.add(user)
            action = "created"

        db.session.commit()
        click.echo(f"Admin user {action}: {email}")

    return app
