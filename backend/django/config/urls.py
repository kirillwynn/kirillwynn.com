import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from apps.core.views import local_account_surface_disabled

django_admin_url = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip("/")

urlpatterns = [
    path("accounts/login/", local_account_surface_disabled),
    path("accounts/logout/", local_account_surface_disabled),
    path("accounts/inactive/", local_account_surface_disabled),
    path("accounts/signup/", local_account_surface_disabled),
    path("accounts/reauthenticate/", local_account_surface_disabled),
    path("accounts/email/", local_account_surface_disabled),
    path("accounts/confirm-email/", local_account_surface_disabled),
    path("accounts/password/change/", local_account_surface_disabled),
    path("accounts/password/set/", local_account_surface_disabled),
    path("accounts/password/reset/", local_account_surface_disabled),
    path("accounts/password/reset/done/", local_account_surface_disabled),
    path("accounts/password/reset/key/done/", local_account_surface_disabled),
    path("accounts/password/reset/confirm/", local_account_surface_disabled),
    path("accounts/password/reset/complete/", local_account_surface_disabled),
    path("accounts/login/code/", local_account_surface_disabled),
    path("accounts/login/code/confirm/", local_account_surface_disabled),
    path("accounts/signup/passkey/", local_account_surface_disabled),
    path("accounts/phone/verify/", local_account_surface_disabled),
    path("accounts/phone/change/", local_account_surface_disabled),
    # The Google provider registers an optional browser-token login endpoint.
    # This project accepts only the server-side OAuth authorization-code flow;
    # browser-supplied provider tokens are never an identity boundary.
    path("accounts/google/login/token/", local_account_surface_disabled),
    re_path(
        r"^accounts/(?:3rdparty|social|2fa|sessions)(?:/.*)?$",
        local_account_surface_disabled,
    ),
    re_path(r"^accounts/confirm-email/[-:\w]+/$", local_account_surface_disabled),
    re_path(
        r"^accounts/password/reset/key/[0-9A-Za-z]+-.+/$",
        local_account_surface_disabled,
    ),
    path("accounts/", include("allauth.urls")),
    # The versioned Stage 17 account API is canonical for browser clients.
    # Keeping the legacy /api/auth/ include in apps.core preserves rollback
    # compatibility, while /api/v1/ traverses the already-active staging edge
    # boundary without broadening it with a generic auth proxy.
    path(
        "api/v1/auth/",
        include("apps.users.api.urls", namespace="users_api_v1"),
    ),
    path("api/v1/", include("apps.subscriptions.api.urls")),
    path("api/v1/", include("apps.discussions.api.urls")),
    path("api/v1/", include("apps.blog.api.urls")),
    path("api/", include("apps.core.urls")),
    path(f"{django_admin_url}/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("media/documents/", include(wagtaildocs_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
