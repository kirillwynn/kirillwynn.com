# kw/app/routes/main.py

import os
import json
from flask import Blueprint, redirect, render_template, current_app
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect('feed')

@main_bp.route('/feed')
def feed():
    return render_template('feed.html')

@main_bp.route('/stack')
def stack():
    return render_template('stack.html')

@main_bp.route('/bridge')
def bridge():
    json_path = os.path.join(current_app.static_folder, 'data', 'socials.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        socials = json.load(f)['socials']

    socials_sorted = sorted(socials, key=lambda x: x['order'])
    return render_template('bridge.html', socials=socials_sorted)

@main_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return "Webhook is working! Flask app is running."

@main_bp.route('/db-test')
def db_test():
    try:
        result = db.session.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "result": result}, 200
    except SQLAlchemyError as e:
        current_app.logger.error("DB test failed", exc_info=e)
        return {"error": str(e)}, 500

@main_bp.route('/health')
def health():
    return {"status": "ok"}, 200
