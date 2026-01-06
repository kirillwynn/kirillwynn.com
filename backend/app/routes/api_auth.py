# backend/app/routes/api_auth.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func

from ..extensions import csrf
from ..models import User

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")

# Simple in-memory rate limit for login attempts per IP (resets on container restart).
login_attempts = defaultdict(list)
MAX_ATTEMPTS = 10
WINDOW_MINUTES = 15


def _client_ip() -> str:
    # If later you want real IP behind proxy, you can rely on X-Forwarded-For,
    # but only if you trust your nginx and set ProxyFix.
    return request.remote_addr or "unknown"


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": getattr(user, "name", None),
        "is_admin": bool(getattr(user, "is_admin", False)),
    }


@api_auth_bp.get("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False, "user": None}), 200
    return jsonify({"authenticated": True, "user": _user_payload(current_user)}), 200


@api_auth_bp.post("/login")
@csrf.exempt  # for now; we’ll make CSRF-ready client in the next steps
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"ok": False, "error": "email and password are required"}), 400

    ip = _client_ip()
    now = datetime.utcnow()

    # Sliding window
    attempts = login_attempts[ip]
    login_attempts[ip] = [t for t in attempts if now - t < timedelta(minutes=WINDOW_MINUTES)]

    if len(login_attempts[ip]) >= MAX_ATTEMPTS:
        return jsonify({"ok": False, "error": "too many attempts"}), 429

    # Case-insensitive email lookup
    user = User.query.filter(func.lower(User.email) == email).first()

    # Only admins are allowed into the admin SPA
    if user and user.is_admin and user.check_password(password):
        login_attempts.pop(ip, None)
        login_user(user)
        return jsonify({"ok": True, "user": _user_payload(user)}), 200

    login_attempts[ip].append(now)
    return jsonify({"ok": False, "error": "invalid credentials"}), 401


@api_auth_bp.post("/logout")
@csrf.exempt
def logout():
    # Logout is idempotent
    if current_user.is_authenticated:
        logout_user()
    return jsonify({"ok": True}), 200
