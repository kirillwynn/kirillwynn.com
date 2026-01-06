from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/health")
def health():
    """
    Lightweight health endpoint for the frontend.
    Can be used by uptime checks as well.
    """
    return jsonify({"status": "ok"})


@api_bp.get("/auth/me")
def auth_me():
    """
    Return current session user (or anonymous).
    This is the cornerstone for future multi-author UX.
    """
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"authenticated": False, "user": None})

    # Keep payload stable and minimal; don't leak sensitive fields.
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": getattr(current_user, "name", None),
                "is_admin": bool(getattr(current_user, "is_admin", False)),
            },
        }
    )
