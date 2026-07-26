import pytest
from django.conf import settings


def test_custom_user_model_is_configured():
    assert settings.AUTH_USER_MODEL == "users.User"


@pytest.mark.parametrize("path", ["/django-admin/", "/cms/"])
def test_admin_routes_require_authentication(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "login" in response.headers["Location"]
