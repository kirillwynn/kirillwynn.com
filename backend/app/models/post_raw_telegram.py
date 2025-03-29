from ..extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

class PostRawTelegram(db.Model):
    __tablename__ = 'posts_raw_telegram'
    __table_args__ = {'schema': 'posts'}

    id = db.Column(db.Integer, primary_key=True)
    telegram_message_id = db.Column(db.BigInteger, nullable=True)
    channel_id = db.Column(db.BigInteger, nullable=True)
    channel_name = db.Column(db.Text, nullable=True)
    author_id = db.Column(db.BigInteger, nullable=True)
    author_username = db.Column(db.Text, nullable=True)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    text_content = db.Column(db.Text, nullable=True)
    media_links = db.Column(db.ARRAY(db.Text), nullable=True)
    raw_data = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)