from django.urls import path

from apps.core.views import current_user, health_check, logout_session, readiness_check

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("readiness/", readiness_check, name="readiness-check"),
    path("me/", current_user, name="current-user"),
    path("auth/logout/", logout_session, name="logout"),
]
