from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthError, AuthProcess
from django.http import HttpResponseRedirect

from apps.users.return_to import is_safe_return_to


class SiteAccountAdapter(DefaultAccountAdapter):
    def is_safe_url(self, url: str) -> bool:
        return is_safe_return_to(url)

    def get_login_redirect_url(self, request):
        return "/"

    def get_signup_redirect_url(self, request):
        return "/"

    def get_logout_redirect_url(self, request):
        return "/"


class SiteSocialAccountAdapter(DefaultSocialAccountAdapter):
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
                    self._error_redirect(
                        request,
                        "already_connected",
                        process=process,
                    )
                )

        if sociallogin.account.pk:
            return

        verified_addresses = [
            address for address in sociallogin.email_addresses if address.verified
        ]
        if not verified_addresses:
            raise ImmediateHttpResponse(
                self._error_redirect(
                    request,
                    "verified_email_required",
                    process=sociallogin.state.get("process"),
                )
            )

        verified_email = verified_addresses[0].email.lower()
        if sociallogin.user and sociallogin.user.pk:
            email_address, _ = EmailAddress.objects.update_or_create(
                user=sociallogin.user,
                email__iexact=verified_email,
                defaults={"email": verified_email, "verified": True},
            )
            if not EmailAddress.objects.filter(user=sociallogin.user, primary=True).exists():
                email_address.primary = True
                email_address.save(update_fields=["primary"])

            if sociallogin._did_authenticate_by_email and process != AuthProcess.CONNECT:
                sociallogin.connect(request, sociallogin.user)
        elif sociallogin.user:
            sociallogin.user.email = verified_email

    def save_user(self, request, sociallogin, form=None):
        if sociallogin.user:
            sociallogin.user.email = sociallogin.user.email.lower()
        return super().save_user(request, sociallogin, form=form)

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
