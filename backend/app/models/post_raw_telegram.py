from ..extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

class PostRawTelegram(db.Model):
    __tablename__ = 'posts_raw_telegram'
    __table_args__ = {'schema': 'posts'}

    id = db.Column(db.Integer, primary_key=True)

    telegram_message_id = db.Column(db.BigInteger, nullable=False)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=False)

    channel_id = db.Column(db.BigInteger, nullable=False)
    channel_name = db.Column(db.Text, nullable=True)
    channel_username = db.Column(db.Text, nullable=True)

    author_id = db.Column(db.BigInteger, nullable=True)
    author_username = db.Column(db.Text, nullable=True)

    text_content = db.Column(db.Text, nullable=True)
    caption = db.Column(db.Text, nullable=True)

    media_type = db.Column(db.Text, nullable=True)
    file_id = db.Column(db.Text, nullable=True)
    file_unique_id = db.Column(db.Text, nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    mime_type = db.Column(db.Text, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    duration = db.Column(db.Integer, nullable=True)

    photo = db.Column(JSONB, nullable=True)

    sticker_emoji = db.Column(db.Text, nullable=True)
    sticker_set_name = db.Column(db.Text, nullable=True)
    is_animated = db.Column(db.Boolean, nullable=True)
    is_video = db.Column(db.Boolean, nullable=True)

    poll_id = db.Column(db.Text, nullable=True)
    poll_question = db.Column(db.Text, nullable=True)
    poll_options = db.Column(JSONB, nullable=True)
    poll_total_voter_count = db.Column(db.Integer, nullable=True)
    poll_is_anonymous = db.Column(db.Boolean, nullable=True)
    poll_is_closed = db.Column(db.Boolean, nullable=True)
    poll_allows_multiple_answers = db.Column(db.Boolean, nullable=True)

    location_latitude = db.Column(db.Float, nullable=True)
    location_longitude = db.Column(db.Float, nullable=True)

    media_links = db.Column(db.ARRAY(db.Text), nullable=True)
    raw_data = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("telegram_message_id", "channel_id", name="uq_message_channel"),
        {'schema': 'posts'}
    )
