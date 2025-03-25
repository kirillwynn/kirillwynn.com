import os
import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import Flask, redirect, render_template

app = Flask(__name__)

db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")
db_port = os.getenv("DB_PORT")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

required = {
    "DB_HOST": db_host, 
    "DB_PORT": db_port,
    "DB_NAME": db_name,
    "DB_USER": db_user, 
    "DB_PASSWORD": db_password
}

missing = [k for k,v in required.items() if not v]
if missing:
    raise RuntimeError(f"Missing required ENV vars: {', '.join(missing)}")

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY is required")

db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

@app.route('/')
def index():
    return redirect('feed')

@app.route('/feed')
def feed():
    return render_template('feed.html')

@app.route('/stack')
def stack():
    return render_template('stack.html')

@app.route('/bridge')
def bridge():
    json_path = os.path.join(app.static_folder, 'data', 'socials.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        socials = json.load(f)['socials']
        
    socials_sorted = sorted(socials, key=lambda x: x['order'])
    return render_template('bridge.html', socials=socials_sorted)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    return "Webhook is working! Flask app is running."

@app.route('/db-test')
def db_test():
    try:
        result = db.session.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "result": result}, 200
    except SQLAlchemyError as e:
        app.logger.error("DB test failed", exc_info=e)
        return {"error": str(e)}, 500

@app.route('/health')
def health():
    return {"status": "ok"}, 200
