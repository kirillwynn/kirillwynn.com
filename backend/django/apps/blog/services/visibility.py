from django.db.models import Q
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
        .select_related("open_graph_image")
        .prefetch_related("tags", "open_graph_image__renditions")
        .order_by("-first_published_at", "-pk")
    )
