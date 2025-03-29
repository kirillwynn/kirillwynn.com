from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.post_raw_telegram import PostRawTelegram
import datetime

telegram_bp = Blueprint('telegram', __name__)

@telegram_bp.route('/webhook/<token>', methods=['POST'])
def telegram_webhook(token):
    expected_token = current_app.config.get('TELEGRAM_WEBHOOK_TOKEN')
    if token != expected_token:
        return jsonify({"ok": False, "error": "Invalid token"}), 403

    update = request.get_json(silent=True)
    if not update:
        return jsonify({"ok": False, "error": "No JSON provided"}), 400

    channel_post = update.get('channel_post')
    if channel_post:
        message_id = channel_post.get('message_id')
        chat = channel_post.get('chat', {})
        channel_id = chat.get('id')

        exists = PostRawTelegram.query.filter_by(
            telegram_message_id=message_id,
            channel_id=channel_id
        ).first()
        if exists:
            return jsonify({"ok": True, "duplicate": True}), 200

        channel_name = chat.get('username') or chat.get('title')
        date_unix = channel_post.get('date')
        posted_at = datetime.datetime.utcfromtimestamp(date_unix) if date_unix else None
        text_content = channel_post.get('text')

        media_links = []
        if 'photo' in channel_post:
            for photo in channel_post['photo']:
                media_links.append(photo.get('file_id'))

        post = PostRawTelegram(
            telegram_message_id=message_id,
            channel_id=channel_id,
            channel_name=channel_name,
            posted_at=posted_at,
            text_content=text_content,
            media_links=media_links if media_links else None,
            raw_data=update
        )

        try:
            db.session.add(post)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to save Telegram post: {e}")
            db.session.rollback()
            return jsonify({"ok": False, "error": "DB error"}), 500

    return jsonify({"ok": True}), 200
