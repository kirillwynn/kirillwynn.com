from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = "Promote an existing verified social user configured by SITE_OWNER_EMAIL."

    @transaction.atomic
    def handle(self, *args, **options):
        email = settings.SITE_OWNER_EMAIL.strip().lower()
        if not email:
            raise CommandError("SITE_OWNER_EMAIL is not configured.")
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError("SITE_OWNER_EMAIL is not a valid email address.") from error

        user_model = get_user_model()
        try:
            user = user_model.objects.select_for_update().get(email__iexact=email)
        except user_model.DoesNotExist as error:
            raise CommandError("No existing user matches SITE_OWNER_EMAIL.") from error

        has_verified_email = EmailAddress.objects.filter(
            user=user,
            email__iexact=email,
            verified=True,
        ).exists()
        has_supported_identity = SocialAccount.objects.filter(
            user=user,
            provider__in=["google", "github"],
        ).exists()
        if not has_verified_email or not has_supported_identity:
            raise CommandError(
                "The site owner must first complete a verified Google or GitHub signup."
            )

        changed = not user.is_staff or not user.is_superuser
        if changed:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
            self.stdout.write(self.style.SUCCESS("Site owner permissions granted."))
        else:
            self.stdout.write("Site owner already has administrator permissions.")
