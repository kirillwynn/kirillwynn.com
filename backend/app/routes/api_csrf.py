# backend/app/routes/api_csrf.py
#
# CSRF token endpoint for SPA clients.
# Returns a CSRF token that must be sent back in a header for unsafe methods.

from flask import Blueprint, jsonify
from flask_wtf.csrf import generate_csrf

api_csrf_bp = Blueprint("api_csrf", __name__)


@api_csrf_bp.get("/api/csrf")
def get_csrf():
    return jsonify({"ok": True, "csrf_token": generate_csrf()})
