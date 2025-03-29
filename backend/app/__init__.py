import os
from flask import Flask
from .config import Config
from .extensions import db, migrate
from .routes.main import main_bp
from backend.app.routes.telegram import telegram_bp

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)

app.register_blueprint(main_bp)
app.register_blueprint(telegram_bp, url_prefix='/telegram')
