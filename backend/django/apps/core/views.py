from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.db import connection
from django.http import HttpResponseNotFound, JsonResponse
from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.users.identity import InvalidNickname, normalize_nickname
from apps.users.services import (
    can_interact,
    has_verified_primary_email,
    nickname_change_available_at,
    profile_complete,
    public_display_name,
)


def private_no_store(response):
    patch_cache_control(response, private=True, no_store=True)
    patch_vary_headers(response, ["Cookie"])
    return response


def csrf_failure(request, reason=""):
    """Return bounded JSON for APIs while preserving Django's admin page."""

    if request.path.startswith("/api/"):
        return private_no_store(JsonResponse({"detail": "CSRF verification failed."}, status=403))
    from django.views.csrf import csrf_failure as django_csrf_failure

    return django_csrf_failure(request, reason=reason)


def local_account_surface_disabled(request, *args, **kwargs):
    """Keep allauth ownership without exposing its duplicate HTML account UI."""

    return HttpResponseNotFound()


def provider_states(user):
    connected = set()
    if user.is_authenticated:
        connected = set(SocialAccount.objects.filter(user=user).values_list("provider", flat=True))
    return {
        provider: {
            "available": bool(settings.SOCIALACCOUNT_PROVIDERS.get(provider, {}).get("APPS")),
            "connected": provider in connected,
        }
        for provider in ("google", "github")
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return Response({"status": "unavailable"}, status=503)
    return Response({"status": "ready"})


@ensure_csrf_cookie
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def current_user(request):
    user = request.user
    payload = {
        "authenticated": user.is_authenticated,
        "user": None,
        "providers": provider_states(user),
        "csrf_token": get_token(request),
    }
    if user.is_authenticated:
        available_at = nickname_change_available_at(user)
        suggestion = None
        if not profile_complete(user):
            try:
                provider_name = " ".join(
                    part.strip() for part in (user.first_name, user.last_name) if part.strip()
                )
                suggestion = normalize_nickname(provider_name).display
            except InvalidNickname:
                pass
        payload["user"] = {
            "id": user.pk,
            "nickname": public_display_name(user),
            "display_name": public_display_name(user),
            "nickname_suggestion": suggestion,
            "email": user.email_normalized,
            "email_verified": has_verified_primary_email(user),
            "profile_complete": profile_complete(user),
            "has_usable_password": user.has_usable_password(),
            "nickname_change_available_at": (available_at.isoformat() if available_at else None),
            "is_admin": user.is_staff or user.is_superuser,
            "is_banned": user.is_banned,
            "can_interact": can_interact(user),
        }
    return private_no_store(Response(payload))
