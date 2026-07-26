import os

from django.contrib import admin
from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

django_admin_url = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip("/")

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("api/v1/", include("apps.discussions.api.urls")),
    path("api/v1/", include("apps.blog.api.urls")),
    path("api/", include("apps.core.urls")),
    path(f"{django_admin_url}/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("media/documents/", include(wagtaildocs_urls)),
]
