from __future__ import annotations

from allauth.account import signals
from allauth.account.forms import LoginForm, SignupForm
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    PermissionDenied,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.subscriptions.rate_limits import client_ip
from apps.users.auth_email import queue_auth_email
from apps.users.credentials import (
    CredentialError,
    confirm_email_credential,
    reset_password_with_credential,
    set_local_password,
)
from apps.users.identity import normalize_email_address, normalize_nickname
from apps.users.models import AuthCredential, NicknameHistory, User
from apps.users.rate_limits import AuthRateLimitExceeded, consume_auth_rate_limit
from apps.users.return_to import safe_return_to
from apps.users.services import change_nickname, has_verified_primary_email, profile_complete

GENERIC_SIGNUP_DETAIL = "If the address can be registered, a verification email will be sent."
GENERIC_EMAIL_DETAIL = "If the account is eligible, an email will be sent."
GENERIC_LOGIN_DETAIL = "The email or password is invalid."


class AuthThrottled(APIException):
    status_code = 429
    default_detail = "Too many requests. Please try again later."
    default_code = "auth_rate_limited"

    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__()


class AuthUnsupportedMediaType(APIException):
    status_code = 415
    default_detail = "Content-Type must be application/json."
    default_code = "unsupported_media_type"


def _form_errors(form):
    errors = {}
    for field, messages in form.errors.get_json_data(escape_html=False).items():
        public_field = {
            "login": "email",
            "password1": "password",
            "password2": "password_confirmation",
        }.get(field, field)
        errors[public_field] = [item["message"] for item in messages]
    return errors


def _validate_payload(request, *, allowed, required=()):
    if request.content_type != "application/json":
        raise UnsupportedMediaType(request.content_type or "unknown")
    if not isinstance(request.data, dict):
        raise ValidationError({"detail": "A JSON object is required."})
    unexpected = set(request.data) - set(allowed)
    if unexpected:
        raise ValidationError({"detail": "Unexpected fields are not allowed."})
    missing = [name for name in sorted(required) if name not in request.data]
    if missing:
        raise ValidationError({name: "This field is required." for name in missing})
    non_strings = [
        name
        for name in sorted(allowed)
        if name in request.data and not isinstance(request.data[name], str)
    ]
    if non_strings:
        raise ValidationError({name: "This field must be a string." for name in non_strings})


def _consume(scope, value):
    try:
        consume_auth_rate_limit(scope=scope, value=value)
    except AuthRateLimitExceeded as error:
        raise AuthThrottled(error.retry_after) from error


def _canonical_or_none(value):
    try:
        return normalize_email_address(value)[1]
    except DjangoValidationError:
        return None


def _credential_error(error):
    status = {"expired": 410, "used": 409, "unavailable": 403}.get(error.code, 400)
    detail = {
        "expired": "This credential has expired.",
        "used": "This credential has already been used.",
        "unavailable": "This account is unavailable.",
    }.get(error.code, "This credential is invalid.")
    return Response({"status": error.code, "detail": detail}, status=status)


class AuthAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    parser_classes = []
    http_method_names = ["post", "patch", "options"]

    def get_parsers(self):
        from apps.users.api.parsers import BoundedJSONParser

        return [BoundedJSONParser()]

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            detail = getattr(exc, "message_dict", None) or {
                "detail": getattr(exc, "messages", ["The request is invalid."])
            }
            exc = ValidationError(detail)
        elif isinstance(exc, DjangoPermissionDenied):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, UnsupportedMediaType):
            # Do not reflect an attacker-controlled Content-Type value.
            exc = AuthUnsupportedMediaType()
        response = super().handle_exception(exc)
        if isinstance(exc, AuthThrottled):
            response["Retry-After"] = str(exc.retry_after)
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True)
        patch_vary_headers(response, ["Cookie"])
        if isinstance(getattr(response, "exception", None), AuthThrottled):
            response["Retry-After"] = str(response.exception.retry_after)
        return response

    @staticmethod
    def require_user(request):
        if not request.user.is_authenticated:
            raise NotAuthenticated("Authentication is required.")
        if not request.user.is_active or request.user.is_banned:
            raise PermissionDenied("This account is unavailable.")
        return request.user


@method_decorator(csrf_protect, name="dispatch")
class LogoutAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(request, allowed=set())
        logout(request)
        return Response(status=204)


@method_decorator(csrf_protect, name="dispatch")
class SignupAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(
            request,
            allowed={"email", "nickname", "password", "password_confirmation"},
            required={"email", "nickname", "password", "password_confirmation"},
        )
        ip = client_ip(request)
        _consume("signup_ip", ip)
        canonical = _canonical_or_none(request.data["email"])
        if canonical:
            _consume("signup_email", canonical)
        form = SignupForm(
            data={
                "email": request.data["email"],
                "nickname": request.data["nickname"],
                "password1": request.data["password"],
                "password2": request.data["password_confirmation"],
            }
        )
        if not form.is_valid():
            return Response({"errors": _form_errors(form)}, status=400)
        normalized = normalize_nickname(form.cleaned_data["nickname"])
        # Nickname availability is intentionally public, but it must be
        # evaluated before the generic existing-email branch. Otherwise a
        # caller could combine a known claimed nickname with candidate emails
        # and distinguish an existing account by the response shape.
        if NicknameHistory.objects.filter(nickname_normalized=normalized.key).exists():
            return Response(
                {"errors": {"nickname": ["This nickname is unavailable."]}},
                status=409,
            )
        if form.account_already_exists:
            return Response({"detail": GENERIC_SIGNUP_DETAIL}, status=202)
        try:
            with transaction.atomic():
                user = form.save(request)
                queue_auth_email(
                    user=user,
                    purpose=AuthCredential.Purpose.VERIFY_EMAIL,
                )
                transaction.on_commit(
                    lambda: signals.user_signed_up.send(
                        sender=User,
                        request=request,
                        user=user,
                    )
                )
        except IntegrityError:
            if User.objects.filter(email_normalized=canonical).exists() if canonical else False:
                return Response({"detail": GENERIC_SIGNUP_DETAIL}, status=202)
            if NicknameHistory.objects.filter(nickname_normalized=normalized.key).exists():
                return Response(
                    {"errors": {"nickname": ["This nickname is unavailable."]}},
                    status=409,
                )
            raise
        return Response({"detail": GENERIC_SIGNUP_DETAIL}, status=202)


@method_decorator(csrf_protect, name="dispatch")
class LoginAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(
            request,
            allowed={"email", "password", "next"},
            required={"email", "password"},
        )
        ip = client_ip(request)
        _consume("login_ip", ip)
        canonical = _canonical_or_none(request.data["email"])
        if canonical:
            _consume("login_email", canonical)
        form = LoginForm(
            request=request,
            data={
                "login": canonical or request.data["email"],
                "password": request.data["password"],
                "remember": True,
            },
        )
        if not form.is_valid() or form.user is None:
            return Response({"detail": GENERIC_LOGIN_DETAIL}, status=400)
        destination = safe_return_to(request.data.get("next"), fallback="/")
        form.login(request, redirect_url=destination)
        if not request.user.is_authenticated:
            return Response({"detail": GENERIC_LOGIN_DETAIL}, status=400)
        return Response(
            {
                "status": "authenticated",
                "next": destination,
                "requires_profile_completion": not profile_complete(request.user),
                "csrf_token": get_token(request),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class ResendVerificationAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(request, allowed={"email"}, required={"email"})
        _consume("resend_ip", client_ip(request))
        canonical = _canonical_or_none(request.data["email"])
        if canonical:
            _consume("resend_email", canonical)
            user = User.objects.filter(email_normalized=canonical).first()
            if user:
                queue_auth_email(
                    user=user,
                    purpose=AuthCredential.Purpose.VERIFY_EMAIL,
                )
        return Response({"detail": GENERIC_EMAIL_DETAIL}, status=202)


@method_decorator(csrf_protect, name="dispatch")
class VerifyEmailAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(request, allowed={"credential"}, required={"credential"})
        _consume("verification_ip", client_ip(request))
        try:
            status = confirm_email_credential(request.data["credential"])
        except CredentialError as error:
            return _credential_error(error)
        return Response({"status": status})


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(request, allowed={"email"}, required={"email"})
        _consume("reset_ip", client_ip(request))
        canonical = _canonical_or_none(request.data["email"])
        if canonical:
            _consume("reset_email", canonical)
            user = User.objects.filter(email_normalized=canonical).first()
            if user:
                queue_auth_email(
                    user=user,
                    purpose=AuthCredential.Purpose.PASSWORD_RESET,
                )
        return Response({"detail": GENERIC_EMAIL_DETAIL}, status=202)


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(
            request,
            allowed={"credential", "password", "password_confirmation"},
            required={"credential", "password", "password_confirmation"},
        )
        _consume("password_credential_ip", client_ip(request))
        try:
            reset_password_with_credential(
                request.data["credential"],
                request.data["password"],
                request.data["password_confirmation"],
            )
        except CredentialError as error:
            return _credential_error(error)
        return Response({"status": "password_reset"})


@method_decorator(csrf_protect, name="dispatch")
class PasswordSetAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(
            request,
            allowed={"password", "password_confirmation"},
            required={"password", "password_confirmation"},
        )
        user = self.require_user(request)
        _consume("password_account_ip", client_ip(request))
        _consume("password_account_user", str(user.pk))
        if user.has_usable_password():
            raise ValidationError({"detail": "A password is already set."})
        if (
            not has_verified_primary_email(user)
            or not SocialAccount.objects.filter(
                user=user,
                provider__in=("google", "github"),
            ).exists()
        ):
            raise PermissionDenied("This account is unavailable.")
        updated = set_local_password(
            user,
            request.data["password"],
            request.data["password_confirmation"],
        )
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, updated)
        return Response({"status": "password_set", "csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class PasswordChangeAPIView(AuthAPIView):
    def post(self, request):
        _validate_payload(
            request,
            allowed={"current_password", "password", "password_confirmation"},
            required={"current_password", "password", "password_confirmation"},
        )
        user = self.require_user(request)
        _consume("password_account_ip", client_ip(request))
        _consume("password_account_user", str(user.pk))
        if not user.has_usable_password():
            raise ValidationError({"detail": "This account has no password to change."})
        updated = set_local_password(
            user,
            request.data["password"],
            request.data["password_confirmation"],
            current_password=request.data["current_password"],
        )
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, updated)
        return Response({"status": "password_changed", "csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class ProfileAPIView(AuthAPIView):
    def patch(self, request):
        _validate_payload(request, allowed={"nickname"}, required={"nickname"})
        user = self.require_user(request)
        _consume("profile_ip", client_ip(request))
        updated = change_nickname(user=user, nickname=request.data["nickname"])
        from apps.users.services import nickname_change_available_at

        available = nickname_change_available_at(updated)
        return Response(
            {
                "status": "profile_complete",
                "nickname": updated.nickname,
                "nickname_change_available_at": (available.isoformat() if available else None),
            }
        )
