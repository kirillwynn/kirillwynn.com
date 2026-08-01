from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.identity import normalize_email_address


class Command(BaseCommand):
    help = "Promote an existing verified social user configured by SITE_OWNER_EMAIL."

    @transaction.atomic
    def handle(self, *args, **options):
        email = settings.SITE_OWNER_EMAIL.strip()
        if not email:
            raise CommandError("SITE_OWNER_EMAIL is not configured.")
        try:
            canonical = normalize_email_address(email)[1]
        except ValidationError as error:
            raise CommandError("SITE_OWNER_EMAIL is not a valid email address.") from error

        user_model = get_user_model()
        candidates = list(
            user_model.objects.select_for_update().filter(email_normalized=canonical)[:2]
        )
        if not candidates:
            # Retain the pre-expansion bootstrap path without weakening the
            # activated canonical identity lookup.
            candidates = []
            for candidate in user_model.objects.select_for_update().filter(
                email_normalized__isnull=True
            ):
                try:
                    candidate_key = normalize_email_address(candidate.email)[1]
                except ValidationError:
                    continue
                if candidate_key == canonical:
                    candidates.append(candidate)
                    if len(candidates) == 2:
                        break
        if not candidates:
            raise CommandError("No existing user matches SITE_OWNER_EMAIL.")
        if len(candidates) != 1:
            raise CommandError("No unique existing user matches SITE_OWNER_EMAIL.")
        user = candidates[0]

        verified_matches = 0
        for address in EmailAddress.objects.select_for_update().filter(
            user=user,
            verified=True,
            primary=True,
        ):
            try:
                address_key = normalize_email_address(address.email)[1]
            except ValidationError:
                continue
            verified_matches += int(address_key == canonical)
        has_verified_email = verified_matches == 1
        has_supported_identity = SocialAccount.objects.filter(
            user=user,
            provider__in=["google", "github"],
        ).exists()
        if not has_verified_email or not has_supported_identity:
            raise CommandError(
                "The site owner must first complete a verified Google or GitHub signup."
            )

        another_site_author = (
            user_model.objects.select_for_update()
            .filter(is_site_author=True)
            .exclude(pk=user.pk)
            .exists()
        )
        if another_site_author:
            raise CommandError("A different site author is already configured.")

        changed = not user.is_staff or not user.is_superuser or not user.is_site_author
        if changed:
            user.is_staff = True
            user.is_superuser = True
            user.is_site_author = True
            user.save(update_fields=["is_staff", "is_superuser", "is_site_author"])
            self.stdout.write(
                self.style.SUCCESS("Site owner permissions granted; author marker set.")
            )
        else:
            self.stdout.write("Site owner already has administrator permissions and author marker.")
