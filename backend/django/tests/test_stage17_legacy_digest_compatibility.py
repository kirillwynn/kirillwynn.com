import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


def test_stage16_user_insert_remains_compatible_with_current_schema():
    """The predecessor model can omit every Stage 17 column on INSERT."""

    executor = MigrationExecutor(connection)
    stage16_apps = executor.loader.project_state([("users", "0001_initial")]).apps
    Stage16User = stage16_apps.get_model("users", "User")

    legacy = Stage16User.objects.create_user(
        username="stage16-overlap-user",
        email="stage16-overlap@example.com",
    )
    current = User.objects.get(pk=legacy.pk)

    assert current.auth_state_version == 1
    assert current.nickname_confirmed is False
    if hasattr(current, "is_site_author"):
        assert current.is_site_author is False
    assert current.email_normalized is None
    assert current.nickname is None
    assert current.nickname_normalized is None

    # This deliberately incomplete expansion-window identity must not leak
    # into another migration or activation-readiness test.
    current.delete()
