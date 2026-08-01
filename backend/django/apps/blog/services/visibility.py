from django.db.models import DateTimeField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.blog.models import BlogPostPage


def public_blog_posts(*, at=None):
    """Return the one canonical public-content policy for blog posts."""

    now = at or timezone.now()
    return (
        BlogPostPage.objects.live()
        .public()
        .filter(first_published_at__isnull=False)
        .filter(Q(go_live_at__isnull=True) | Q(go_live_at__lte=now))
        .filter(Q(expire_at__isnull=True) | Q(expire_at__gt=now))
        .annotate(
            _display_published_at_order=Coalesce(
                "original_published_at",
                "first_published_at",
                output_field=DateTimeField(),
            )
        )
        .select_related("open_graph_image", "owner")
        .prefetch_related("tags", "open_graph_image__renditions")
        .order_by("-_display_published_at_order", "-pk")
    )
