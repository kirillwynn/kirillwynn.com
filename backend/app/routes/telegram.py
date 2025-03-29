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
    if not channel_post:
        return jsonify({"ok": False, "error": "No channel_post found"}), 400

    message_id = channel_post.get('message_id')
    chat = channel_post.get('chat', {})
    sender_chat = channel_post.get('sender_chat', {})

    channel_id = chat.get('id') or sender_chat.get('id')
    channel_name = chat.get('title') or sender_chat.get('title')
    channel_username = chat.get('username') or sender_chat.get('username')

    if not channel_id or not message_id:
        return jsonify({"ok": False, "error": "Missing channel_id or message_id"}), 400

    # Check for duplicate
    exists = PostRawTelegram.query.filter_by(
        telegram_message_id=message_id,
        channel_id=channel_id
    ).first()
    if exists:
        return jsonify({"ok": True, "duplicate": True}), 200

    posted_at = None
    if channel_post.get('date'):
        posted_at = datetime.datetime.utcfromtimestamp(channel_post['date'])

    text_content = channel_post.get('text')
    caption = channel_post.get('caption')

    # Author
    author_id = sender_chat.get('id')
    author_username = sender_chat.get('username')

    # Media
    media_type = None
    file_id = None
    file_unique_id = None
    file_size = None
    mime_type = None
    width = None
    height = None
    duration = None
    media_links = []

    # Photo
    photo = channel_post.get('photo')
    if photo:
        media_type = 'photo'
        media_links = [p.get('file_id') for p in photo if 'file_id' in p]
        best_photo = photo[-1] if photo else {}
        file_id = best_photo.get('file_id')
        file_unique_id = best_photo.get('file_unique_id')
        file_size = best_photo.get('file_size')
        width = best_photo.get('width')
        height = best_photo.get('height')

    # Voice
    elif 'voice' in channel_post:
        voice = channel_post['voice']
        media_type = 'voice'
        file_id = voice.get('file_id')
        file_unique_id = voice.get('file_unique_id')
        file_size = voice.get('file_size')
        mime_type = voice.get('mime_type')
        duration = voice.get('duration')

    # Video note
    elif 'video_note' in channel_post:
        video = channel_post['video_note']
        media_type = 'video_note'
        file_id = video.get('file_id')
        file_unique_id = video.get('file_unique_id')
        file_size = video.get('file_size')
        duration = video.get('duration')
        width = video.get('length')
        height = video.get('length')

    # Sticker
    elif 'sticker' in channel_post:
        sticker = channel_post['sticker']
        media_type = 'sticker'
        file_id = sticker.get('file_id')
        file_unique_id = sticker.get('file_unique_id')
        file_size = sticker.get('file_size')
        width = sticker.get('width')
        height = sticker.get('height')
        mime_type = sticker.get('mime_type')
        sticker_emoji = sticker.get('emoji')
        sticker_set_name = sticker.get('set_name')
        is_animated = sticker.get('is_animated')
        is_video = sticker.get('is_video')
    else:
        sticker_emoji = sticker_set_name = is_animated = is_video = None

    # Poll
    poll = channel_post.get('poll')
    if poll:
        poll_id = poll.get('id')
        poll_question = poll.get('question')
        poll_options = poll.get('options')
        poll_total_voter_count = poll.get('total_voter_count')
        poll_is_anonymous = poll.get('is_anonymous')
        poll_is_closed = poll.get('is_closed')
        poll_allows_multiple_answers = poll.get('allows_multiple_answers')
    else:
        poll_id = poll_question = poll_options = poll_total_voter_count = None
        poll_is_anonymous = poll_is_closed = poll_allows_multiple_answers = None

    # Location
    location = channel_post.get('location')
    location_latitude = location.get('latitude') if location else None
    location_longitude = location.get('longitude') if location else None

    post = PostRawTelegram(
        telegram_message_id=message_id,
        posted_at=posted_at,
        channel_id=channel_id,
        channel_name=channel_name,
        channel_username=channel_username,
        author_id=author_id,
        author_username=author_username,
        text_content=text_content,
        caption=caption,
        media_type=media_type,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_size=file_size,
        mime_type=mime_type,
        width=width,
        height=height,
        duration=duration,
        photo=photo,
        sticker_emoji=sticker_emoji,
        sticker_set_name=sticker_set_name,
        is_animated=is_animated,
        is_video=is_video,
        poll_id=poll_id,
        poll_question=poll_question,
        poll_options=poll_options,
        poll_total_voter_count=poll_total_voter_count,
        poll_is_anonymous=poll_is_anonymous,
        poll_is_closed=poll_is_closed,
        poll_allows_multiple_answers=poll_allows_multiple_answers,
        location_latitude=location_latitude,
        location_longitude=location_longitude,
        media_links=media_links or None,
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
