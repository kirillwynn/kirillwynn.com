from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import logout
from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def private_no_store(response):
    patch_cache_control(response, private=True, no_store=True)
    patch_vary_headers(response, ["Cookie"])
    return response


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
        payload["user"] = {
            "id": user.pk,
            "display_name": user.get_full_name().strip() or user.username,
            "email": user.email,
            "is_admin": user.is_staff or user.is_superuser,
            "is_banned": user.is_banned,
            "can_interact": user.is_active and not user.is_banned,
        }
    return private_no_store(Response(payload))


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([AllowAny])
def logout_session(request):
    logout(request)
    return private_no_store(Response(status=204))
