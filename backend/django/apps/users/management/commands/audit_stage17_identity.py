import json

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from apps.blog.models import BlogPostPage
from apps.blog.services.visibility import public_blog_posts
from apps.discussions.models import Comment, CommentReaction, PostReaction
from apps.users.identity import (
    InvalidNickname,
    normalize_email_address,
    normalize_nickname,
)
from apps.users.models import NicknameHistory, User


class Command(BaseCommand):
    help = "Emit a non-sensitive Stage 17 identity expansion audit report."

    def add_arguments(self, parser):
        parser.add_argument("--require-activation-ready", action="store_true")

    def handle(self, *args, **options):
        site_author_rows = list(
            User.objects.filter(is_site_author=True)
            .order_by("pk")
            .values_list("pk", "nickname")[:2]
        )
        site_author_ids = [user_id for user_id, _nickname in site_author_rows]
        site_author_nicknames = tuple(
            nickname for _user_id, nickname in site_author_rows if nickname
        )
        invalid_nickname_ids = []
        invalid_email_ids = []
        mismatched_email_ids = []
        for user in User.objects.exclude(nickname__isnull=True).order_by("pk"):
            try:
                legacy_privileged = bool(
                    user.is_staff or user.is_superuser or user.pk in site_author_ids
                )
                normalized = normalize_nickname(
                    user.nickname,
                    reserved_values=site_author_nicknames,
                    allow_reserved=legacy_privileged,
                )
            except InvalidNickname:
                invalid_nickname_ids.append(user.pk)
                continue
            if normalized.key != user.nickname_normalized:
                invalid_nickname_ids.append(user.pk)

        for user in User.objects.order_by("pk"):
            try:
                email_key = normalize_email_address(user.email)[1]
            except ValidationError:
                invalid_email_ids.append(user.pk)
                continue
            if email_key != user.email_normalized:
                mismatched_email_ids.append(user.pk)

        duplicate_nickname_keys = list(
            User.objects.exclude(nickname_normalized__isnull=True)
            .values("nickname_normalized")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
            .values_list("nickname_normalized", flat=True)
        )
        duplicate_email_keys = list(
            User.objects.exclude(email_normalized__isnull=True)
            .values("email_normalized")
            .annotate(total=Count("pk"))
            .filter(total__gt=1)
            .values_list("email_normalized", flat=True)
        )
        duplicate_email_user_ids = list(
            User.objects.filter(email_normalized__in=duplicate_email_keys)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        nickname_claims = set(NicknameHistory.objects.values_list("user_id", "nickname_normalized"))
        missing_nickname_claim_user_ids = [
            user_id
            for user_id, nickname_key in User.objects.exclude(nickname_normalized__isnull=True)
            .order_by("pk")
            .values_list("pk", "nickname_normalized")
            if (user_id, nickname_key) not in nickname_claims
        ]
        verified_primary_user_ids = set()
        mismatched_primary_user_ids = []
        mismatched_verified_primary_user_ids = []
        address_owners = {}
        duplicate_address_ids = set()
        duplicate_address_user_ids = set()
        invalid_address_ids = []
        verified_address_owners = {}
        duplicate_verified_address_ids = set()
        duplicate_verified_address_user_ids = set()
        invalid_verified_address_ids = []
        for address in EmailAddress.objects.select_related("user").order_by("pk"):
            try:
                address_key = normalize_email_address(address.email)[1]
            except ValidationError:
                invalid_address_ids.append(address.pk)
                if address.verified:
                    invalid_verified_address_ids.append(address.pk)
                if address.primary:
                    mismatched_primary_user_ids.append(address.user_id)
                    if address.verified:
                        mismatched_verified_primary_user_ids.append(address.user_id)
                continue

            prior = address_owners.get(address_key)
            if prior is not None:
                prior_owner, prior_address_id = prior
                duplicate_address_ids.update((prior_address_id, address.pk))
                duplicate_address_user_ids.update((prior_owner, address.user_id))
            else:
                address_owners[address_key] = (address.user_id, address.pk)

            if address.primary:
                if address_key == address.user.email_normalized:
                    if address.verified:
                        verified_primary_user_ids.add(address.user_id)
                else:
                    mismatched_primary_user_ids.append(address.user_id)
                    if address.verified:
                        mismatched_verified_primary_user_ids.append(address.user_id)

            if not address.verified:
                continue
            verified_prior = verified_address_owners.get(address_key)
            if verified_prior is not None:
                prior_owner, prior_address_id = verified_prior
                duplicate_verified_address_ids.update((prior_address_id, address.pk))
                if prior_owner != address.user_id:
                    duplicate_verified_address_user_ids.update((prior_owner, address.user_id))
            else:
                verified_address_owners[address_key] = (address.user_id, address.pk)
        public_posts = public_blog_posts().select_related(None).prefetch_related(None)
        ownerless_post_ids = list(
            public_posts.filter(owner_id__isnull=True).values_list("pk", flat=True)
        )
        all_ownerless_post_ids = list(
            BlogPostPage.objects.filter(owner_id__isnull=True)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        null_identity_ids = list(
            User.objects.filter(
                Q(email_normalized__isnull=True)
                | Q(nickname__isnull=True)
                | Q(nickname_normalized__isnull=True)
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        confirmed_ids = set(
            User.objects.filter(nickname_confirmed=True).values_list("pk", flat=True)
        )
        social_token_count = SocialToken.objects.count()
        report = {
            "schema": "stage17-identity-audit/v2",
            "users": {
                "total": User.objects.count(),
                "nickname_populated": User.objects.filter(nickname__isnull=False).count(),
                "nickname_confirmed": len(confirmed_ids),
                "profile_incomplete": User.objects.filter(nickname_confirmed=False).count(),
                "email_key_populated": User.objects.filter(email_normalized__isnull=False).count(),
                "verified_primary": len(verified_primary_user_ids),
                "unverified_or_missing_primary": User.objects.count()
                - len(verified_primary_user_ids),
                "verified_and_profile_complete": len(verified_primary_user_ids & confirmed_ids),
                "usable_password": sum(
                    1 for user in User.objects.only("password") if user.has_usable_password()
                ),
                "inactive": User.objects.filter(is_active=False).count(),
                "banned": User.objects.filter(is_banned=True).count(),
                "staff": User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
                .distinct()
                .count(),
                "site_author_ids": site_author_ids[:100],
            },
            "audit": {
                "nickname_history": NicknameHistory.objects.count(),
                "invalid_nickname_user_ids": invalid_nickname_ids[:100],
                "invalid_email_user_ids": invalid_email_ids[:100],
                "mismatched_email_user_ids": mismatched_email_ids[:100],
                "mismatched_primary_email_address_user_ids": sorted(
                    set(mismatched_primary_user_ids)
                )[:100],
                "mismatched_verified_primary_user_ids": mismatched_verified_primary_user_ids[:100],
                "invalid_email_address_ids": invalid_address_ids[:100],
                "duplicate_email_address_ids": sorted(duplicate_address_ids)[:100],
                "duplicate_email_address_user_ids": sorted(duplicate_address_user_ids)[:100],
                "invalid_verified_email_address_ids": invalid_verified_address_ids[:100],
                "duplicate_verified_email_address_ids": sorted(duplicate_verified_address_ids)[
                    :100
                ],
                "duplicate_verified_email_address_user_ids": sorted(
                    duplicate_verified_address_user_ids
                )[:100],
                "null_identity_user_ids": null_identity_ids[:100],
                "missing_nickname_claim_user_ids": missing_nickname_claim_user_ids[:100],
                "duplicate_nickname_keys": duplicate_nickname_keys[:100],
                "duplicate_email_key_count": len(duplicate_email_keys),
                "duplicate_email_user_ids": duplicate_email_user_ids[:100],
            },
            "preserved_relations": {
                "database_sessions": Session.objects.count(),
                "social_accounts": SocialAccount.objects.count(),
                "social_tokens": social_token_count,
                "comments": Comment.objects.count(),
                "post_reactions": PostReaction.objects.count(),
                "comment_reactions": CommentReaction.objects.count(),
            },
            "posts": {
                "public": public_posts.count(),
                "distinct_owner_count": public_posts.exclude(owner_id__isnull=True)
                .values("owner_id")
                .distinct()
                .count(),
                "distinct_owner_ids": list(
                    public_posts.exclude(owner_id__isnull=True)
                    .order_by("owner_id")
                    .values_list("owner_id", flat=True)
                    .distinct()[:100]
                ),
                "ownerless_ids": ownerless_post_ids[:100],
                "all_ownerless_ids": all_ownerless_post_ids[:100],
            },
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))

        blocking = bool(
            invalid_nickname_ids
            or invalid_email_ids
            or mismatched_email_ids
            or mismatched_primary_user_ids
            or mismatched_verified_primary_user_ids
            or invalid_address_ids
            or duplicate_address_ids
            or invalid_verified_address_ids
            or duplicate_verified_address_ids
            or duplicate_verified_address_user_ids
            or duplicate_nickname_keys
            or duplicate_email_keys
            or missing_nickname_claim_user_ids
            or social_token_count
            or all_ownerless_post_ids
            or (User.objects.exists() and len(site_author_ids) != 1)
        )
        if options["require_activation_ready"] and (blocking or null_identity_ids):
            raise CommandError("Stage 17 identity expansion is not activation-ready")
