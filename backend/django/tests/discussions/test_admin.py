import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory

from apps.discussions.admin import CommentAdmin
from apps.discussions.models import Comment
from apps.discussions.services import create_top_level_comment
from apps.users.admin import ProjectUserAdmin
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_comment_admin_disables_add_and_hard_delete(public_post, user, admin_user):
    comment = create_top_level_comment(post=public_post, author=user, body="Preserved")
    request = RequestFactory().get("/django-admin/discussions/comment/")
    request.user = admin_user
    model_admin = CommentAdmin(Comment, site)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_delete_permission(request, comment) is False
    assert model_admin.actions == ("hide_comments", "unhide_comments")


def test_user_admin_exposes_ban_and_unban_actions(admin_user, user):
    request = RequestFactory().post("/django-admin/users/user/")
    request.user = admin_user
    model_admin = ProjectUserAdmin(User, site)

    model_admin.ban_users(request, User.objects.filter(pk=user.pk))
    user.refresh_from_db()
    assert user.is_banned is True

    model_admin.unban_users(request, User.objects.filter(pk=user.pk))
    user.refresh_from_db()
    assert user.is_banned is False
