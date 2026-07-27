from django.db import transaction
from django.dispatch import receiver
from wagtail.search.index import insert_or_update_object
from wagtail.signals import page_published, page_unpublished

from apps.blog.models import BlogPostPage, RevalidationEvent
from apps.blog.services.revalidation import create_revalidation_event, deliver_event_after_commit


@receiver(page_published, sender=BlogPostPage, dispatch_uid="blog_post_revalidation_published")
def blog_post_published(sender, instance, **kwargs):
    # Page post-save indexing runs before cluster child relations from a
    # revision are fully copied. Reindex at page_published so tag names are
    # present in the database search document.
    insert_or_update_object(instance)
    with transaction.atomic():
        event = create_revalidation_event(instance)
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
