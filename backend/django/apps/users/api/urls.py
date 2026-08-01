from django.urls import path

from apps.users.api.views import (
    LoginAPIView,
    LogoutAPIView,
    PasswordChangeAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    PasswordSetAPIView,
    ProfileAPIView,
    ResendVerificationAPIView,
    SignupAPIView,
    VerifyEmailAPIView,
)

app_name = "users_api"

urlpatterns = [
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("signup/", SignupAPIView.as_view(), name="signup"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("verify-email/", VerifyEmailAPIView.as_view(), name="verify-email"),
    path(
        "verify-email/resend/",
        ResendVerificationAPIView.as_view(),
        name="resend-verification",
    ),
    path(
        "password/reset/",
        PasswordResetRequestAPIView.as_view(),
        name="password-reset",
    ),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="password-reset-confirm",
    ),
    path("password/set/", PasswordSetAPIView.as_view(), name="password-set"),
    path("password/change/", PasswordChangeAPIView.as_view(), name="password-change"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
]
