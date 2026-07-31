from wagtail.permissions import ModelPermissionPolicy
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.discussions.models import ReactionCatalogItem


class ManifestManagedCatalogPermissionPolicy(ModelPermissionPolicy):
    """The admin can curate manifest-owned rows, but cannot create or destroy them."""

    def user_has_permission(self, user, action):
        if action in {"add", "delete"}:
            return False
        return super().user_has_permission(user, action)

    def user_has_permission_for_instance(self, user, action, instance):
        if action in {"add", "delete"}:
            return False
        return super().user_has_permission_for_instance(user, action, instance)


class ReactionCatalogItemViewSet(SnippetViewSet):
    model = ReactionCatalogItem
    icon = "pick"
    menu_label = "Reaction catalog"
    menu_order = 850
    menu_item_is_registered = True
    copy_view_enabled = False
    inspect_view_enabled = True
    list_display = (
        "catalog_id",
        "display_name",
        "kind",
        "enabled",
        "selectable",
        "ordering",
        "quick_order",
        "approval_status",
    )
    list_filter = ("kind", "enabled", "selectable", "approval_status")
    search_fields = ("catalog_id", "display_name", "accessibility_label")
    ordering = ("ordering", "catalog_id")
    form_fields = (
        "display_name",
        "accessibility_label",
        "ordering",
        "enabled",
        "selectable",
    )
    inspect_view_fields = (
        "catalog_id",
        "kind",
        "source_sha256",
        "normalized_sha256",
        "poster_sha256",
        "immutable_asset_version",
        "intrinsic_width",
        "intrinsic_height",
        "frame_count",
        "duration_ms",
        "minimum_frame_delay_ms",
        "asset_storage_key",
        "poster_storage_key",
        "provenance_source",
        "provenance_author",
        "license",
        "rights_basis",
        "approval_status",
        "manifest_sha256",
        "imported_at",
    )

    @property
    def permission_policy(self):
        return ManifestManagedCatalogPermissionPolicy(self.model)


register_snippet(ReactionCatalogItemViewSet)
