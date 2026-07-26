import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.db import IntegrityError
from django.utils import timezone
from wagtail_headless_preview.models import PagePreview

from apps.blog.models import BlogPostPage, PreviewSnapshot

PREVIEW_SIGNING_SALT = "kirillwynn.preview-snapshot.v1"


class InvalidPreviewCredential(Exception):
    pass


def _credential_digest(credential):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        credential.encode(),
        hashlib.sha256,
    ).hexdigest()


def _preview_signer():
    return signing.TimestampSigner(salt=PREVIEW_SIGNING_SALT)


def issue_preview_credential(*, package_token, expected_page):
    PreviewSnapshot.objects.filter(
        created_at__lt=timezone.now() - timedelta(seconds=settings.PREVIEW_TOKEN_TTL_SECONDS * 2)
    ).delete()

    try:
        package_preview = PagePreview.objects.select_related("content_type").get(
            token=package_token
        )
    except PagePreview.DoesNotExist as error:
        raise InvalidPreviewCredential from error

    expected_content_type = ContentType.objects.get_for_model(
        expected_page,
        for_concrete_model=False,
    )
    if package_preview.content_type_id != expected_content_type.pk:
        raise InvalidPreviewCredential

    try:
        content = json.loads(package_preview.content_json)
    except (TypeError, ValueError) as error:
        raise InvalidPreviewCredential from error
    if content.get("content_type") != expected_content_type.pk:
        raise InvalidPreviewCredential
    if content.get("pk") != expected_page.pk:
        raise InvalidPreviewCredential

    for _ in range(3):
        credential = _preview_signer().sign(secrets.token_urlsafe(32))
        try:
            PreviewSnapshot.objects.create(
                credential_digest=_credential_digest(credential),
                content_type=expected_content_type,
                page_id=expected_page.pk,
                content_json=package_preview.content_json,
            )
        except IntegrityError:
            continue
        return credential

    raise RuntimeError("Could not create a unique preview credential")


def resolve_preview_credential(credential):
    if not isinstance(credential, str) or not 40 <= len(credential) <= 255:
        raise InvalidPreviewCredential

    try:
        _preview_signer().unsign(
            credential,
            max_age=settings.PREVIEW_TOKEN_TTL_SECONDS,
        )
    except (signing.BadSignature, signing.SignatureExpired) as error:
        raise InvalidPreviewCredential from error

    try:
        snapshot = PreviewSnapshot.objects.select_related("content_type").get(
            credential_digest=_credential_digest(credential)
        )
    except PreviewSnapshot.DoesNotExist as error:
        raise InvalidPreviewCredential from error

    expected_content_type = ContentType.objects.get_for_model(
        BlogPostPage,
        for_concrete_model=False,
    )
    if snapshot.content_type_id != expected_content_type.pk:
        raise InvalidPreviewCredential

    try:
        content = json.loads(snapshot.content_json)
    except (TypeError, ValueError) as error:
        raise InvalidPreviewCredential from error
    if content.get("content_type") != expected_content_type.pk:
        raise InvalidPreviewCredential
    if content.get("pk") != snapshot.page_id:
        raise InvalidPreviewCredential

    page = BlogPostPage.from_json(snapshot.content_json)
    page.pk = snapshot.page_id
    return page
