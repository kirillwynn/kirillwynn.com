import os
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(DATABASE_URL)

@app.route('/')
def hello():
    return "Hello, world! Flask app is running."

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return "Webhook is working! Flask app is running."

@app.route('/db-test')
def db_test():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            return f"DB connection successful: {result}"
    except SQLAlchemyError as e:
        return f"DB connection error: {e}"