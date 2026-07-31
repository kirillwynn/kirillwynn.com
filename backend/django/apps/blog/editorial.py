from dataclasses import dataclass
from enum import StrEnum

from apps.blog.models import BlogIndexPage, BlogPostPage


class NewPostTargetStatus(StrEnum):
    READY = "ready"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class NewPostTarget:
    status: NewPostTargetStatus
    parent: BlogIndexPage | None = None
    message: str = ""

    @property
    def available(self):
        return self.status == NewPostTargetStatus.READY and self.parent is not None


def resolve_new_post_target(user):
    """Resolve the one valid Blog index without relying on a deployed page ID."""

    candidates = list(BlogIndexPage.objects.order_by("pk"))
    if not candidates:
        return NewPostTarget(
            NewPostTargetStatus.MISSING,
            message=(
                "New post is unavailable because the Blog index is missing. "
                "Restore the BlogIndexPage before creating posts."
            ),
        )
    if len(candidates) != 1:
        return NewPostTarget(
            NewPostTargetStatus.AMBIGUOUS,
            message=(
                "New post is unavailable because more than one Blog index exists. "
                "Repair the page tree before continuing."
            ),
        )

    parent = candidates[0]
    tree_parent = parent.get_parent()
    if tree_parent is None or not tree_parent.is_root() or not BlogPostPage.can_create_at(parent):
        return NewPostTarget(
            NewPostTargetStatus.INVALID,
            message=(
                "New post is unavailable because the Blog index is outside its expected "
                "place in the page tree."
            ),
        )

    if not parent.permissions_for_user(user).can_add_subpage():
        return NewPostTarget(
            NewPostTargetStatus.FORBIDDEN,
            message="You do not have permission to add a post beneath the Blog index.",
        )

    return NewPostTarget(NewPostTargetStatus.READY, parent=parent)
