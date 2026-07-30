import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory

from apps.discussions.admin import CommentAdmin, ReactionAdmin
from apps.discussions.models import Comment, PostReaction, ReactionCatalogItem
from apps.discussions.services import create_top_level_comment
from apps.discussions.wagtail_hooks import ReactionCatalogItemViewSet
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


def test_reaction_catalog_wagtail_viewset_is_manifest_managed(admin_user):
    viewset = ReactionCatalogItemViewSet()
    policy = viewset.permission_policy

    assert policy.user_has_permission(admin_user, "change") is True
    assert policy.user_has_permission(admin_user, "add") is False
    assert policy.user_has_permission(admin_user, "delete") is False
    assert viewset.copy_view_enabled is False
    assert set(viewset.get_form_fields()) == {
        "display_name",
        "accessibility_label",
        "ordering",
        "enabled",
        "selectable",
    }
    assert {
        "asset_storage_key",
        "poster_storage_key",
        "normalized_sha256",
        "immutable_asset_version",
    }.isdisjoint(viewset.get_form_fields())
    assert viewset.model is ReactionCatalogItem


def test_reaction_admin_keeps_both_identity_fields_read_only(admin_user):
    request = RequestFactory().post("/django-admin/discussions/postreaction/")
    request.user = admin_user
    model_admin = ReactionAdmin(PostReaction, site)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    assert {"catalog_item", "emoji"}.issubset(model_admin.readonly_fields)
