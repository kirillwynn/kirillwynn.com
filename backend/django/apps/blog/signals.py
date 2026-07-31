from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from wagtail.models import Page, PageViewRestriction
from wagtail.search.index import insert_or_update_object
from wagtail.signals import page_published, page_unpublished

from apps.blog.models import BlogPostPage, RevalidationEvent
from apps.blog.services.revalidation import create_revalidation_event, deliver_event_after_commit
from apps.blog.services.visibility import public_blog_posts
from apps.subscriptions.outbox import decide_publication_email


def _live_blog_posts_at_or_below(page):
    return BlogPostPage.objects.live().descendant_of(page, inclusive=True)


def _restriction_was_removed_directly(origin):
    if origin is None or isinstance(origin, PageViewRestriction):
        return True
    origin_model = getattr(origin, "model", None)
    if origin_model is not None:
        return not issubclass(origin_model, Page)
    return not isinstance(origin, Page)


@receiver(page_published, sender=BlogPostPage, dispatch_uid="blog_post_revalidation_published")
def blog_post_published(sender, instance, **kwargs):
    # Page post-save indexing runs before cluster child relations from a
    # revision are fully copied. Reindex at page_published so tag names are
    # present in the database search document.
    insert_or_update_object(instance)
    with transaction.atomic():
        event = create_revalidation_event(instance)
        decide_publication_email(instance)
        deliver_event_after_commit(event.pk)


@receiver(page_unpublished, sender=BlogPostPage, dispatch_uid="blog_post_revalidation_unpublished")
def blog_post_unpublished(sender, instance, **kwargs):
    action = (
        RevalidationEvent.Action.EXPIRED
        if instance.expired
        else RevalidationEvent.Action.UNPUBLISHED
    )
    with transaction.atomic():
        event = create_revalidation_event(instance, action=action)
        deliver_event_after_commit(event.pk)


@receiver(
    post_save,
    sender=PageViewRestriction,
    dispatch_uid="blog_post_view_restriction_saved",
)
def blog_post_view_restriction_saved(sender, instance, **kwargs):
    try:
        page = instance.page
    except ObjectDoesNotExist:
        return

    with transaction.atomic():
        for post in _live_blog_posts_at_or_below(page).select_for_update():
            event = create_revalidation_event(
                post,
                action=RevalidationEvent.Action.UNPUBLISHED,
            )
            deliver_event_after_commit(event.pk)


@receiver(
    post_delete,
    sender=PageViewRestriction,
    dispatch_uid="blog_post_view_restriction_deleted",
)
def blog_post_view_restriction_deleted(sender, instance, **kwargs):
    if not _restriction_was_removed_directly(kwargs.get("origin")):
        return
    try:
        page = instance.page
    except ObjectDoesNotExist:
        return

    with transaction.atomic():
        candidate_ids = _live_blog_posts_at_or_below(page).values_list("pk", flat=True)
        public_candidates = (
            public_blog_posts()
            .filter(pk__in=candidate_ids)
            # The public Feed queryset eagerly loads an optional image through
            # a LEFT JOIN. PostgreSQL cannot lock an unspecified nullable join
            # side, and signal processing needs only the post rows.
            .select_related(None)
            .prefetch_related(None)
            .select_for_update()
        )
        for post in public_candidates:
            event = create_revalidation_event(post)
            decide_publication_email(post)
            deliver_event_after_commit(event.pk)
