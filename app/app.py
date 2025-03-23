# Minimal Flask application to display a greeting message

from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, world! Flask app is running."
