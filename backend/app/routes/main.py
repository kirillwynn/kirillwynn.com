import json
import os

from flask import Blueprint, abort, current_app, render_template, request
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Post
from ..utils.sanitizer import generate_excerpt

main_bp = Blueprint('main', __name__)


@main_bp.route('/feed')
def feed():
    posts = (
        Post.query.filter_by(status="published")
        .order_by(Post.published_at.desc().nullslast(), Post.created_at.desc())
        .all()
    )
    return render_template('feed.html', posts=posts, excerpt=generate_excerpt)


@main_bp.route('/stash')
def stash():
    return render_template('stash.html')


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


@main_bp.route('/posts/<slug>')
def post_detail(slug: str):
    post = Post.query.filter_by(slug=slug).first_or_404()
    is_preview_allowed = (
        current_user.is_authenticated
        and current_user.is_admin
        and request.args.get("preview") == "1"
    )

    if post.status != "published" and not is_preview_allowed:
        abort(404)

    return render_template('post_detail.html', post=post)
