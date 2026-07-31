from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from wagtail.models import PageViewRestriction

from apps.blog.models import BlogPostPage
from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    PostPublicationEmailDecision,
    Subscriber,
)
from apps.subscriptions.providers.memory import MemoryEmailProvider

pytestmark = pytest.mark.django_db


def publish(page):
    page.save_revision().publish()
    return BlogPostPage.objects.get(pk=page.pk)


def publication_events(post):
    return EmailOutbox.objects.filter(
        post=post,
        message_type=EmailOutbox.MessageType.PUBLICATION,
    )


def test_newsletter_checkbox_defaults_on_and_pending_status_is_read_only(blog_post):
    form_class = BlogPostPage.get_edit_handler().get_form_class()
    form = form_class(instance=blog_post)

    assert blog_post.notify_subscribers_on_first_publication is True
    assert form["notify_subscribers_on_first_publication"].value() is True
    assert form.fields["notify_subscribers_on_first_publication"].disabled is False
    assert blog_post.newsletter_status.startswith("Pending")


def test_suppressed_archive_is_durable_across_republish_slug_change_and_rollback(blog_post):
    MemoryEmailProvider.reset()
    notification_enabled_revision = blog_post.save_revision()
    blog_post.original_published_at = datetime(2012, 5, 4, tzinfo=UTC)
    blog_post.notify_subscribers_on_first_publication = False
    published = publish(blog_post)
    decision = PostPublicationEmailDecision.objects.get(post=published)
    decided_at = decision.decided_at

    assert decision.state == PostPublicationEmailDecision.State.SUPPRESSED
    assert decision.outbox_id is None
    assert publication_events(published).count() == 0
    assert EmailDelivery.objects.count() == 0
    assert MemoryEmailProvider.sent == []

    published.slug = "suppressed-archive-renamed"
    published.notify_subscribers_on_first_publication = True
    publish(published)
    notification_enabled_revision.as_object().save_revision().publish()

    decision.refresh_from_db()
    assert decision.state == PostPublicationEmailDecision.State.SUPPRESSED
    assert decision.decided_at == decided_at
    assert decision.outbox_id is None
    assert publication_events(published).count() == 0
    assert EmailDelivery.objects.count() == 0
    assert MemoryEmailProvider.sent == []

    current = BlogPostPage.objects.get(pk=published.pk)
    form = BlogPostPage.get_edit_handler().get_form_class()(instance=current)
    assert form.fields["notify_subscribers_on_first_publication"].disabled is True
    assert form.fields["notify_subscribers_on_first_publication"].initial is False
    assert form["notify_subscribers_on_first_publication"].value() is False
    assert current.newsletter_status.startswith("Suppressed")


def test_enabled_first_publication_uses_actual_cutoff_and_creates_exactly_one_event(blog_post):
    archive_date = datetime(2008, 1, 2, 3, 4, tzinfo=UTC)
    blog_post.original_published_at = archive_date
    before = timezone.now()

    published = publish(blog_post)
    after = timezone.now()
    decision = PostPublicationEmailDecision.objects.get(post=published)
    event = publication_events(published).get()

    assert decision.state == PostPublicationEmailDecision.State.QUEUED
    assert decision.outbox_id == event.pk
    assert decision.decided_at == event.audience_cutoff
    assert before <= event.audience_cutoff <= after
    assert event.audience_cutoff != archive_date
    assert event.available_at == event.audience_cutoff

    published.title = "Republished title"
    publish(published)
    decision.refresh_from_db()
    event.refresh_from_db()

    assert publication_events(published).count() == 1
    assert decision.outbox_id == event.pk
    assert decision.decided_at == event.audience_cutoff


@pytest.mark.parametrize(
    ("notify", "expected_state", "expected_events"),
    [
        (True, PostPublicationEmailDecision.State.QUEUED, 1),
        (False, PostPublicationEmailDecision.State.SUPPRESSED, 0),
    ],
)
def test_restricted_post_waits_for_direct_public_transition(
    blog_post,
    notify,
    expected_state,
    expected_events,
):
    blog_post.notify_subscribers_on_first_publication = notify
    restriction = PageViewRestriction.objects.create(
        page=blog_post,
        restriction_type=PageViewRestriction.PASSWORD,
        password="test-only",
    )

    published = publish(blog_post)
    pending = PostPublicationEmailDecision.objects.get(post=published)
    assert pending.state == PostPublicationEmailDecision.State.PENDING
    assert pending.decided_at is None
    assert publication_events(published).count() == 0

    restriction.delete()
    pending.refresh_from_db()

    assert pending.state == expected_state
    assert pending.decided_at is not None
    assert publication_events(published).count() == expected_events
    assert EmailDelivery.objects.count() == 0


def test_ancestor_restriction_waits_and_then_decides_for_descendant_post(
    blog_post,
    blog_index,
):
    blog_post.notify_subscribers_on_first_publication = False
    restriction = PageViewRestriction.objects.create(
        page=blog_index,
        restriction_type=PageViewRestriction.PASSWORD,
        password="test-only",
    )

    published = publish(blog_post)
    decision = PostPublicationEmailDecision.objects.get(post=published)
    assert decision.state == PostPublicationEmailDecision.State.PENDING
    assert not publication_events(published).exists()

    restriction.delete()
    decision.refresh_from_db()

    assert decision.state == PostPublicationEmailDecision.State.SUPPRESSED
    assert decision.decided_at is not None
    assert not publication_events(published).exists()


def test_deleting_restricted_post_does_not_treat_cascade_as_public_transition(
    blog_post,
):
    PageViewRestriction.objects.create(
        page=blog_post,
        restriction_type=PageViewRestriction.PASSWORD,
        password="test-only",
    )
    published = publish(blog_post)
    post_id = published.pk
    assert PostPublicationEmailDecision.objects.get(post=published).state == "pending"

    published.delete()

    assert not BlogPostPage.objects.filter(pk=post_id).exists()
    assert not PostPublicationEmailDecision.objects.filter(post_id=post_id).exists()
    assert not EmailOutbox.objects.filter(
        post_id=post_id,
        message_type=EmailOutbox.MessageType.PUBLICATION,
    ).exists()


def test_future_scheduled_post_waits_for_worker_and_then_locks_decision(blog_post):
    due = timezone.now() + timedelta(minutes=5)
    blog_post.go_live_at = due
    blog_post.notify_subscribers_on_first_publication = False
    blog_post.save_revision(approved_go_live_at=due).publish()

    assert not publication_events(blog_post).exists()
    assert blog_post.newsletter_status.startswith("Pending")

    past_due = timezone.now() - timedelta(minutes=1)
    scheduled = BlogPostPage.objects.get(pk=blog_post.pk)
    scheduled.go_live_at = past_due
    scheduled.save_revision(approved_go_live_at=past_due)
    call_command("publish_scheduled_pages", verbosity=0)

    decision = PostPublicationEmailDecision.objects.get(post_id=blog_post.pk)
    assert decision.state == PostPublicationEmailDecision.State.SUPPRESSED
    assert decision.decided_at is not None
    assert not publication_events(blog_post).exists()


def test_suppression_never_creates_delivery_or_invokes_provider(blog_post):
    active_at = timezone.now() - timedelta(days=1)
    Subscriber.objects.create(
        email="reader@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=active_at,
    )
    blog_post.notify_subscribers_on_first_publication = False
    MemoryEmailProvider.reset()

    published = publish(blog_post)
    call_command("process_email_outbox", limit=10, verbosity=0)

    assert PostPublicationEmailDecision.objects.get(post=published).state == "suppressed"
    assert not publication_events(published).exists()
    assert not EmailDelivery.objects.exists()
    assert MemoryEmailProvider.sent == []


def test_decision_database_constraint_rejects_invalid_state_shape(blog_post):
    with pytest.raises(IntegrityError), transaction.atomic():
        PostPublicationEmailDecision.objects.create(
            post=blog_post,
            state=PostPublicationEmailDecision.State.QUEUED,
            decided_at=timezone.now(),
            outbox=None,
        )
