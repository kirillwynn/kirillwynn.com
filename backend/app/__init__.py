import os
import click
from flask import Flask, redirect, url_for
from .config import Config
from .extensions import csrf, db, login_manager, migrate
from .models import User
from .routes.main import main_bp
from .routes.admin import admin_bp

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def root_redirect():
        return redirect(url_for("main.feed"))

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
