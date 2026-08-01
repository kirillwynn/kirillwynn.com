import json

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q

from apps.blog.services.visibility import public_blog_posts
from apps.discussions.models import Comment, CommentReaction, PostReaction
from apps.users.identity import InvalidNickname, normalize_nickname
from apps.users.models import NicknameHistory, User


class Command(BaseCommand):
    help = "Emit a non-sensitive Stage 17 identity expansion audit report."

    def add_arguments(self, parser):
        parser.add_argument("--require-activation-ready", action="store_true")

    def handle(self, *args, **options):
        invalid_nickname_ids = []
        for user in User.objects.exclude(nickname__isnull=True).order_by("pk"):
            try:
                normalized = normalize_nickname(user.nickname, allow_reserved=True)
            except InvalidNickname:
                invalid_nickname_ids.append(user.pk)
                continue
            if normalized.key != user.nickname_normalized:
                invalid_nickname_ids.append(user.pk)

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
        verified_primary_user_ids = set(
            EmailAddress.objects.filter(primary=True, verified=True).values_list(
                "user_id", flat=True
            )
        )
        public_posts = public_blog_posts().select_related(None).prefetch_related(None)
        ownerless_post_ids = list(
            public_posts.filter(owner_id__isnull=True).values_list("pk", flat=True)
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
        report = {
            "schema": "stage17-identity-audit/v1",
            "users": {
                "total": User.objects.count(),
                "nickname_populated": User.objects.filter(nickname__isnull=False).count(),
                "nickname_confirmed": len(confirmed_ids),
                "profile_incomplete": User.objects.filter(nickname_confirmed=False).count(),
                "email_key_populated": User.objects.filter(email_normalized__isnull=False).count(),
                "verified_primary": len(verified_primary_user_ids),
                "verified_and_profile_complete": len(verified_primary_user_ids & confirmed_ids),
                "usable_password": sum(
                    1 for user in User.objects.only("password") if user.has_usable_password()
                ),
                "inactive": User.objects.filter(is_active=False).count(),
                "banned": User.objects.filter(is_banned=True).count(),
                "staff": User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
                .distinct()
                .count(),
            },
            "audit": {
                "nickname_history": NicknameHistory.objects.count(),
                "invalid_nickname_user_ids": invalid_nickname_ids[:100],
                "null_identity_user_ids": null_identity_ids[:100],
                "duplicate_nickname_keys": duplicate_nickname_keys[:100],
                "duplicate_email_keys": duplicate_email_keys[:100],
            },
            "preserved_relations": {
                "database_sessions": Session.objects.count(),
                "social_accounts": SocialAccount.objects.count(),
                "social_tokens": SocialToken.objects.count(),
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
                "ownerless_ids": ownerless_post_ids[:100],
            },
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))

        blocking = bool(
            invalid_nickname_ids
            or duplicate_nickname_keys
            or duplicate_email_keys
            or ownerless_post_ids
        )
        if options["require_activation_ready"] and (blocking or null_identity_ids):
            raise CommandError("Stage 17 identity expansion is not activation-ready")
