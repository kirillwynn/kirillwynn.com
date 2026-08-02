#!/usr/bin/env python3
"""Emit a bounded, PII-free integrity report for active or restored staging data."""

import json
import re
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.conf import settings
from django.contrib.auth.hashers import identify_hasher
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.blog.models import BlogPostPage, RevalidationEvent
from apps.blog.services.visibility import public_blog_posts
from apps.discussions.models import (
    Comment,
    CommentReaction,
    PostReaction,
    ReactionCatalogItem,
    ReactionSettings,
)
from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    EmailWebhookEvent,
    PostPublicationEmailDecision,
    Subscriber,
)
from apps.users.identity import normalize_email_address
from apps.users.models import (
    AuthCredential,
    AuthEmailDelivery,
    AuthEmailOutbox,
    NicknameHistory,
    User,
)
from apps.users.services import is_site_author, public_display_name

EXPECTED_CATALOG_ITEMS = 228
EXPECTED_CATALOG_MANIFEST_SHA256 = (
    "1b0a409b80ddb46eed4059a19210eec82f5444530eb268a33d5cb0945e08c018"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def grouped_counts(queryset, field):
    return {
        row[field]: row["total"]
        for row in queryset.values(field).annotate(total=Count("pk")).order_by(field)
    }


def add_violation(violations, name, count):
    if count:
        violations[name] = count


def build_report():
    now = timezone.now()
    stale_window = timedelta(
        seconds=max(getattr(settings, "EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS", 300), 300)
    )
    stale_before = now - stale_window
    public_pages = list(
        public_blog_posts()
        .select_related(None)
        .prefetch_related(None)
        .select_related("owner")
        .only(
            "pk",
            "owner_id",
            "owner__nickname",
            "owner__nickname_normalized",
            "owner__is_site_author",
        )
    )
    public_ids = [page.pk for page in public_pages]

    author_mismatches = 0
    for page in public_pages:
        if page.owner_id is None:
            continue
        author = {
            "id": page.owner.pk,
            "display_name": public_display_name(page.owner),
            "is_site_author": is_site_author(page.owner),
        }
        if (
            set(author or {}) != {"id", "display_name", "is_site_author"}
            or author["id"] != page.owner_id
            or author["display_name"] != page.owner.nickname
            or author["is_site_author"] != page.owner.is_site_author
            or not author["display_name"]
        ):
            author_mismatches += 1

    missing_current_claims = sum(
        1
        for user_id, nickname_key in User.objects.exclude(
            nickname_normalized__isnull=True
        ).values_list("pk", "nickname_normalized")
        if not NicknameHistory.objects.filter(
            user_id=user_id,
            nickname_normalized=nickname_key,
        ).exists()
    )
    verified_primary = EmailAddress.objects.filter(
        verified=True,
        primary=True,
    ).select_related("user")
    verified_primary_mismatches = 0
    for address in verified_primary:
        try:
            address_key = normalize_email_address(address.email)[1]
        except ValidationError:
            verified_primary_mismatches += 1
            continue
        if address_key != address.user.email_normalized:
            verified_primary_mismatches += 1

    invalid_comment_shape = (
        Comment.objects.filter(thread_root__isnull=True).exclude(reply_to_user__isnull=True).count()
        + Comment.objects.filter(thread_root__isnull=False, reply_to_user__isnull=True).count()
        + Comment.objects.filter(thread_root__thread_root__isnull=False).count()
        + Comment.objects.filter(thread_root__isnull=False)
        .exclude(post_id=F("thread_root__post_id"))
        .count()
    )
    invalid_post_reaction_identity = PostReaction.objects.filter(
        Q(catalog_item__isnull=True, emoji="") | Q(catalog_item__isnull=False) & ~Q(emoji="")
    ).count()
    invalid_comment_reaction_identity = CommentReaction.objects.filter(
        Q(catalog_item__isnull=True, emoji="") | Q(catalog_item__isnull=False) & ~Q(emoji="")
    ).count()

    catalog_hashes = list(
        ReactionCatalogItem.objects.order_by().values_list("manifest_sha256", flat=True).distinct()
    )
    quick_items = list(
        ReactionCatalogItem.objects.exclude(quick_order__isnull=True)
        .order_by("quick_order")
        .values_list("catalog_id", "quick_order")
    )
    settings_rows = list(ReactionSettings.objects.order_by("pk"))
    settings_quick_ids = []
    if len(settings_rows) == 1:
        settings_quick_ids = [
            settings_rows[0].quick_reaction_item_one_id,
            settings_rows[0].quick_reaction_item_two_id,
            settings_rows[0].quick_reaction_item_three_id,
        ]
    quick_relation_mismatches = int(
        len(settings_rows) != 1
        or len(quick_items) != 3
        or [catalog_id for catalog_id, _order in quick_items] != settings_quick_ids
        or [order for _catalog_id, order in quick_items] != [1, 2, 3]
    )

    decision_queryset = PostPublicationEmailDecision.objects.filter(post_id__in=public_ids)
    publication_decision_count = decision_queryset.count()
    queued_decision_mismatches = (
        decision_queryset.filter(state="queued")
        .exclude(
            outbox__message_type="publication",
            outbox__post_id=F("post_id"),
        )
        .count()
    )
    suppressed_decision_mismatches = (
        decision_queryset.filter(state="suppressed").exclude(outbox__isnull=True).count()
    )

    future_scheduled = BlogPostPage.objects.filter(
        live=False,
        go_live_at__gt=now,
    ).count()
    due_unpublished = BlogPostPage.objects.filter(
        live=False,
        go_live_at__isnull=False,
        go_live_at__lte=now,
    ).count()
    expired_live = BlogPostPage.objects.filter(
        live=True,
        expire_at__isnull=False,
        expire_at__lte=now,
    ).count()

    publication_outbox_stale = EmailOutbox.objects.filter(
        status="pending",
        available_at__lte=stale_before,
    ).count()
    publication_processing_stale = EmailOutbox.objects.filter(
        status="processing",
        processing_at__lte=stale_before,
    ).count()
    delivery_stale = EmailDelivery.objects.filter(
        status="pending",
        available_at__lte=stale_before,
    ).count()
    delivery_processing_stale = EmailDelivery.objects.filter(
        status="processing",
        processing_at__lte=stale_before,
    ).count()
    auth_outbox_stale = AuthEmailOutbox.objects.filter(
        status="pending",
        available_at__lte=stale_before,
    ).count()
    auth_outbox_processing_stale = AuthEmailOutbox.objects.filter(
        status="processing",
        processing_at__lte=stale_before,
    ).count()
    auth_delivery_stale = AuthEmailDelivery.objects.filter(
        status="pending",
        available_at__lte=stale_before,
    ).count()
    auth_delivery_processing_stale = AuthEmailDelivery.objects.filter(
        status="processing",
        processing_at__lte=stale_before,
    ).count()
    webhook_expired_pending = EmailWebhookEvent.objects.filter(
        processing_state="pending",
        expires_at__lte=now,
    ).count()
    revalidation_stale = RevalidationEvent.objects.filter(
        Q(state="pending", created_at__lte=stale_before)
        | Q(state="processing", last_attempt_at__lte=stale_before)
    ).count()

    invalid_auth_credential_digests = sum(
        1
        for digest in AuthCredential.objects.values_list("credential_digest", flat=True)
        if SHA256.fullmatch(digest) is None
    )
    invalid_password_storage = 0
    for encoded in User.objects.values_list("password", flat=True):
        if encoded.startswith("!"):
            continue
        try:
            identify_hasher(encoded)
        except ValueError:
            invalid_password_storage += 1

    violations = {}
    add_violation(
        violations,
        "site_author_count",
        abs(User.objects.filter(is_site_author=True).count() - 1),
    )
    add_violation(violations, "missing_current_nickname_claims", missing_current_claims)
    add_violation(violations, "verified_primary_mismatches", verified_primary_mismatches)
    add_violation(violations, "social_tokens", SocialToken.objects.count())
    add_violation(
        violations,
        "ownerless_posts",
        BlogPostPage.objects.filter(owner_id__isnull=True).count(),
    )
    add_violation(violations, "public_author_serializer_mismatches", author_mismatches)
    add_violation(violations, "invalid_comment_shape", invalid_comment_shape)
    add_violation(violations, "invalid_post_reaction_identity", invalid_post_reaction_identity)
    add_violation(
        violations,
        "invalid_comment_reaction_identity",
        invalid_comment_reaction_identity,
    )
    add_violation(
        violations,
        "catalog_item_count",
        abs(ReactionCatalogItem.objects.count() - EXPECTED_CATALOG_ITEMS),
    )
    add_violation(
        violations,
        "catalog_manifest_hash",
        int(catalog_hashes != [EXPECTED_CATALOG_MANIFEST_SHA256]),
    )
    add_violation(
        violations,
        "catalog_not_staging_only",
        ReactionCatalogItem.objects.exclude(approval_status="staging-only/unverified").count(),
    )
    add_violation(
        violations,
        "catalog_not_enabled_selectable",
        ReactionCatalogItem.objects.exclude(enabled=True, selectable=True).count(),
    )
    add_violation(violations, "quick_relation_mismatches", quick_relation_mismatches)
    add_violation(
        violations,
        "public_publication_decision_count",
        abs(publication_decision_count - len(public_ids)),
    )
    add_violation(
        violations,
        "public_pending_publication_decisions",
        decision_queryset.filter(state="pending").count(),
    )
    add_violation(violations, "queued_decision_mismatches", queued_decision_mismatches)
    add_violation(
        violations,
        "suppressed_decision_mismatches",
        suppressed_decision_mismatches,
    )
    add_violation(violations, "due_scheduled_pages", due_unpublished)
    add_violation(violations, "expired_live_pages", expired_live)
    add_violation(violations, "stale_email_outbox", publication_outbox_stale)
    add_violation(
        violations,
        "stale_processing_email_outbox",
        publication_processing_stale,
    )
    add_violation(violations, "stale_email_deliveries", delivery_stale)
    add_violation(
        violations,
        "stale_processing_email_deliveries",
        delivery_processing_stale,
    )
    add_violation(violations, "stale_auth_email_outbox", auth_outbox_stale)
    add_violation(
        violations,
        "stale_processing_auth_email_outbox",
        auth_outbox_processing_stale,
    )
    add_violation(violations, "stale_auth_email_deliveries", auth_delivery_stale)
    add_violation(
        violations,
        "stale_processing_auth_email_deliveries",
        auth_delivery_processing_stale,
    )
    add_violation(violations, "expired_pending_webhooks", webhook_expired_pending)
    add_violation(violations, "stale_revalidation_events", revalidation_stale)
    add_violation(
        violations,
        "invalid_auth_credential_digests",
        invalid_auth_credential_digests,
    )
    add_violation(violations, "invalid_password_storage", invalid_password_storage)

    return {
        "schema": "stage18-staging-data-audit/v1",
        "migrations": {
            "applied": MigrationRecorder.Migration.objects.count(),
            "leaves": [
                f"{app}.{name}"
                for app, name in sorted(MigrationLoader(connection).graph.leaf_nodes())
            ],
        },
        "identity": {
            "users": User.objects.count(),
            "verified_emails": EmailAddress.objects.filter(verified=True).count(),
            "verified_primary_emails": verified_primary.count(),
            "nickname_claims": NicknameHistory.objects.count(),
            "social_accounts": SocialAccount.objects.count(),
            "social_account_owners": SocialAccount.objects.values("user_id").distinct().count(),
            "social_tokens": SocialToken.objects.count(),
            "sessions": Session.objects.count(),
        },
        "posts": {
            "total": BlogPostPage.objects.count(),
            "public": len(public_ids),
            "ownerless": BlogPostPage.objects.filter(owner_id__isnull=True).count(),
            "public_author_serializer_mismatches": author_mismatches,
            "future_scheduled": future_scheduled,
            "due_unpublished": due_unpublished,
            "expired_live": expired_live,
        },
        "discussions": {
            "comments": Comment.objects.count(),
            "roots": Comment.objects.filter(thread_root__isnull=True).count(),
            "replies": Comment.objects.filter(thread_root__isnull=False).count(),
            "deleted_tombstones": Comment.objects.filter(deleted_at__isnull=False).count(),
            "hidden_tombstones": Comment.objects.filter(moderation_state="hidden").count(),
            "post_reactions": PostReaction.objects.count(),
            "comment_reactions": CommentReaction.objects.count(),
            "legacy_unicode_post_reactions": PostReaction.objects.filter(
                catalog_item__isnull=True
            ).count(),
            "legacy_unicode_comment_reactions": CommentReaction.objects.filter(
                catalog_item__isnull=True
            ).count(),
        },
        "reaction_catalog": {
            "items": ReactionCatalogItem.objects.count(),
            "enabled_selectable": ReactionCatalogItem.objects.filter(
                enabled=True,
                selectable=True,
            ).count(),
            "animated": ReactionCatalogItem.objects.filter(kind="animated").count(),
            "quick_relations": len(quick_items),
            "manifest_hash_matches": catalog_hashes == [EXPECTED_CATALOG_MANIFEST_SHA256],
            "rights_statuses": grouped_counts(ReactionCatalogItem.objects.all(), "approval_status"),
        },
        "subscriptions": {
            "subscribers": grouped_counts(Subscriber.objects.all(), "status"),
            "publication_decisions": grouped_counts(
                PostPublicationEmailDecision.objects.all(),
                "state",
            ),
            "outbox": grouped_counts(EmailOutbox.objects.all(), "status"),
            "deliveries": grouped_counts(EmailDelivery.objects.all(), "status"),
            "webhooks": grouped_counts(EmailWebhookEvent.objects.all(), "processing_state"),
        },
        "auth_email": {
            "credentials": grouped_counts(AuthCredential.objects.all(), "purpose"),
            "outbox": grouped_counts(AuthEmailOutbox.objects.all(), "status"),
            "deliveries": grouped_counts(AuthEmailDelivery.objects.all(), "status"),
        },
        "revalidation": grouped_counts(RevalidationEvent.objects.all(), "state"),
        "violations": violations,
    }


def main():
    if connection.vendor != "postgresql":
        raise SystemExit("Stage 18 staging data audit requires PostgreSQL")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        report = build_report()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if report["violations"]:
        raise SystemExit(1)


main()
