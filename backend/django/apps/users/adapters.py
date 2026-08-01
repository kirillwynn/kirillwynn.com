import uuid
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthError, AuthProcess
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.utils import timezone

from apps.users.identity import normalize_email_address, normalize_nickname
from apps.users.models import AuthCredential
from apps.users.return_to import is_safe_return_to
from apps.users.services import (
    claim_initial_nickname,
    normalize_public_nickname,
    profile_complete,
)


def _verified_social_emails(sociallogin):
    verified = []
    for address in sociallogin.email_addresses:
        if not address.verified:
            continue
        try:
            canonical = normalize_email_address(address.email)[1]
        except ValidationError:
            continue
        verified.append((address, canonical))
    return verified


def _locked_matching_email_addresses(user, canonical):
    matches = []
    for address in EmailAddress.objects.select_for_update().filter(user=user).order_by("pk"):
        try:
            address_key = normalize_email_address(address.email)[1]
        except ValidationError:
            continue
        if address_key == canonical:
            matches.append(address)
    return matches


def _retain_authoritative_social_email(sociallogin, address, canonical):
    # Provider profiles may contain extra or differently-normalized addresses.
    # Stage 17 has one public identity mailbox, so only the selected verified
    # canonical address is allowed to reach allauth's EmailAddress persistence.
    address.email = canonical
    address.verified = True
    address.primary = True
    sociallogin.email_addresses = [address]


class SiteAccountAdapter(DefaultAccountAdapter):
    def clean_email(self, email: str) -> str:
        return normalize_email_address(email)[1]

    def populate_username(self, request, user):
        if not user.username:
            user.username = f"usr_{uuid.uuid4().hex}"

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        canonical = self.clean_email(form.cleaned_data["email"])
        normalized = normalize_public_nickname(form.cleaned_data["nickname"], user=user)
        user.email = canonical
        user.email_normalized = canonical
        user.nickname = normalized.display
        user.nickname_normalized = normalized.key
        user.nickname_confirmed = True
        user.nickname_changed_at = None
        if commit:
            user.save()
            from apps.users.models import NicknameHistory

            NicknameHistory.objects.create(
                user=user,
                nickname=normalized.display,
                nickname_normalized=normalized.key,
                change_kind=NicknameHistory.ChangeKind.INITIAL,
            )
        return user

    def authenticate(self, request, **credentials):
        email = credentials.get("email")
        password = credentials.get("password")
        if email is None or password is None:
            return super().authenticate(request, **credentials)
        try:
            canonical = self.clean_email(email)
        except ValidationError:
            canonical = ""
        from apps.users.models import User

        user = User.objects.filter(email_normalized=canonical).first() if canonical else None
        if user is None:
            # Match Django's deliberate dummy hash for an unknown identity.
            User().set_password(password)
            return None
        if not user.check_password(password) or not user.is_active or user.is_banned:
            return None
        return user

    def pre_login(self, request, user, **kwargs):
        if not user.is_active or getattr(user, "is_banned", False):
            return self._unavailable_redirect()
        return super().pre_login(request, user, **kwargs)

    def post_login(self, request, user, **kwargs):
        if not profile_complete(user):
            from apps.users.return_to import safe_return_to

            destination = safe_return_to(kwargs.get("redirect_url"), fallback="/")
            return HttpResponseRedirect(f"/account/profile?{urlencode({'next': destination})}")
        return super().post_login(request, user, **kwargs)

    def is_safe_url(self, url: str) -> bool:
        return is_safe_return_to(url)

    def get_login_redirect_url(self, request):
        return "/"

    def get_signup_redirect_url(self, request):
        return "/"

    def get_logout_redirect_url(self, request):
        return "/"

    @staticmethod
    def _unavailable_redirect():
        return HttpResponseRedirect("/login?error=account_unavailable")


class SiteSocialAccountAdapter(DefaultSocialAccountAdapter):
    def authenticate_by_email(self, sociallogin):
        from apps.users.models import User

        for address, canonical in _verified_social_emails(sociallogin):
            if not self.can_authenticate_by_email(sociallogin, address.email):
                continue
            user = User.objects.filter(email_normalized=canonical).first()
            if user is not None:
                return user, address.email
        return None

    def get_app(self, request, provider, client_id=None):
        from allauth.socialaccount.models import SocialApp

        try:
            return super().get_app(request, provider, client_id=client_id)
        except SocialApp.DoesNotExist as error:
            raise ImmediateHttpResponse(
                self._error_redirect(request, "provider_unavailable")
            ) from error

    def pre_social_login(self, request, sociallogin):
        process = sociallogin.state.get("process")
        if process == AuthProcess.CONNECT and (
            not request.user.is_authenticated
            or not request.user.is_active
            or getattr(request.user, "is_banned", False)
        ):
            raise ImmediateHttpResponse(
                self._error_redirect(request, "account_unavailable", process=process)
            )
        if sociallogin.user and (
            not sociallogin.user.is_active or getattr(sociallogin.user, "is_banned", False)
        ):
            raise ImmediateHttpResponse(
                self._error_redirect(
                    request,
                    "account_unavailable",
                    process=sociallogin.state.get("process"),
                )
            )

        if (
            process == AuthProcess.CONNECT
            and request.user.is_authenticated
            and sociallogin.user
            and sociallogin.user.pk
        ):
            if sociallogin.user != request.user:
                raise ImmediateHttpResponse(
                    self._error_redirect(
                        request,
                        "identity_in_use",
                        process=process,
                    )
                )
            if sociallogin.account.pk:
                raise ImmediateHttpResponse(
                    HttpResponseRedirect("/account?status=already_connected")
                )

        verified_emails = _verified_social_emails(sociallogin)
        if not verified_emails:
            raise ImmediateHttpResponse(
                self._error_redirect(
                    request,
                    "verified_email_required",
                    process=sociallogin.state.get("process"),
                )
            )

        if sociallogin.account.pk:
            selected = next(
                (
                    (address, canonical)
                    for address, canonical in verified_emails
                    if canonical == sociallogin.user.email_normalized
                ),
                None,
            )
            if selected is None:
                # Provider UID alone is not the account boundary in this
                # project. Email change is outside Stage 17, so a linked
                # identity whose provider no longer verifies the Django
                # canonical address fails closed instead of silently drifting.
                raise ImmediateHttpResponse(self._error_redirect(request, "identity_mismatch"))
            _retain_authoritative_social_email(sociallogin, *selected)
            return

        if process == AuthProcess.CONNECT:
            from apps.users.services import has_verified_primary_email

            selected = next(
                (
                    (address, canonical)
                    for address, canonical in verified_emails
                    if canonical == request.user.email_normalized
                ),
                None,
            )
            if not has_verified_primary_email(request.user) or selected is None:
                raise ImmediateHttpResponse(
                    self._error_redirect(request, "identity_mismatch", process=process)
                )
            _retain_authoritative_social_email(sociallogin, *selected)
            return
        if sociallogin.user and sociallogin.user.pk:
            matched_email = sociallogin._did_authenticate_by_email
            matched_key = None
            if matched_email:
                try:
                    matched_key = normalize_email_address(matched_email)[1]
                except ValidationError:
                    matched_key = None
            selected = next(
                (
                    (address, canonical)
                    for address, canonical in verified_emails
                    if canonical == matched_key
                ),
                None,
            )
            if matched_email and selected is None:
                raise ImmediateHttpResponse(
                    self._error_redirect(request, "verified_email_required")
                )
            selected = selected or verified_emails[0]
            selected_address, verified_email = selected
            _retain_authoritative_social_email(
                sociallogin,
                selected_address,
                verified_email,
            )
            try:
                with transaction.atomic():
                    from apps.users.models import User

                    locked = User.objects.select_for_update().get(pk=sociallogin.user.pk)
                    if (
                        not locked.is_active
                        or locked.is_banned
                        or locked.email_normalized != verified_email
                    ):
                        raise ImmediateHttpResponse(
                            self._error_redirect(request, "account_unavailable")
                        )
                    sociallogin.user = locked
                    matching_addresses = _locked_matching_email_addresses(locked, verified_email)
                    if len(matching_addresses) > 1:
                        raise IntegrityError("Ambiguous canonical EmailAddress rows")
                    existing_address = matching_addresses[0] if matching_addresses else None
                    claimed_unverified_identity = sociallogin._did_authenticate_by_email and (
                        existing_address is None or not existing_address.verified
                    )
                    if claimed_unverified_identity:
                        # A verified provider may claim a pre-created
                        # unverified local identity only after any attacker
                        # password/session is destroyed. The attacker-selected
                        # nickname must also be explicitly accepted or replaced
                        # by the verified owner through profile completion.
                        fields = [
                            "password",
                            "nickname_confirmed",
                            "nickname_changed_at",
                            "auth_state_version",
                        ]
                        # Always rotate the unusable-password salt as well as
                        # destroying a usable password. Django sessions bind
                        # to this hash, so even an anomalous OAuth/admin
                        # session on an unverified preregistration is revoked.
                        locked.set_unusable_password()
                        locked.nickname_confirmed = False
                        locked.nickname_changed_at = None
                        locked.auth_state_version += 1
                        locked.save(update_fields=fields)
                        AuthCredential.objects.filter(
                            user=locked,
                            used_at__isnull=True,
                            revoked_at__isnull=True,
                        ).update(revoked_at=timezone.now())
                    EmailAddress.objects.filter(user=locked, primary=True).exclude(
                        pk=existing_address.pk if existing_address else None
                    ).update(primary=False)
                    if existing_address is None:
                        EmailAddress.objects.create(
                            user=locked,
                            email=verified_email,
                            primary=True,
                            verified=True,
                        )
                    else:
                        existing_address.email = verified_email
                        existing_address.primary = True
                        existing_address.verified = True
                        existing_address.save(update_fields=("email", "primary", "verified"))

                    if sociallogin._did_authenticate_by_email and process != AuthProcess.CONNECT:
                        sociallogin.connect(request, locked)
            except IntegrityError:
                raise ImmediateHttpResponse(
                    self._error_redirect(request, "identity_in_use")
                ) from None
        elif sociallogin.user:
            selected_address, verified_email = next(
                (item for item in verified_emails if getattr(item[0], "primary", False)),
                verified_emails[0],
            )
            _retain_authoritative_social_email(
                sociallogin,
                selected_address,
                verified_email,
            )
            sociallogin.user.email = verified_email
            sociallogin.user.email_normalized = verified_email

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if user:
            verified = _verified_social_emails(sociallogin)
            if not verified:
                raise ImmediateHttpResponse(
                    self._error_redirect(request, "verified_email_required")
                )
            _, canonical = next(
                (item for item in verified if getattr(item[0], "primary", False)),
                verified[0],
            )
            user.email = canonical
            user.email_normalized = canonical
            # Provider usernames/UID-derived values are not public identity
            # and must not become a stable internal identifier either.
            user.username = f"usr_{uuid.uuid4().hex}"
            user.nickname = None
            user.nickname_normalized = None
            user.nickname_confirmed = False
        saved = super().save_user(request, sociallogin, form=form)
        if saved and not saved.nickname_confirmed and not saved.nickname_normalized:
            for _attempt in range(5):
                try:
                    saved = claim_initial_nickname(
                        user=saved,
                        nickname=f"user-{uuid.uuid4().hex[:12]}",
                        confirmed=False,
                    )
                    break
                except ValidationError:
                    continue
            else:  # pragma: no cover - UUID collisions are defensive only
                raise RuntimeError("Could not allocate a provisional OAuth nickname")
        return saved

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        suggestion = data.get("name") or " ".join(
            part for part in (data.get("first_name"), data.get("last_name")) if part
        )
        if suggestion:
            try:
                sociallogin.state["nickname_suggestion"] = normalize_nickname(suggestion).display
            except ValidationError:
                pass
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        return "/account"

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        code = "cancelled" if error == AuthError.CANCELLED else "oauth"
        state = (extra_context or {}).get("state") or {}
        raise ImmediateHttpResponse(
            self._error_redirect(request, code, process=state.get("process"))
        )

    @staticmethod
    def _error_redirect(request, code, process=None):
        process = process or request.GET.get("process") or request.POST.get("process")
        destination = "/account" if process == AuthProcess.CONNECT else "/login"
        return HttpResponseRedirect(f"{destination}?{urlencode({'error': code})}")
