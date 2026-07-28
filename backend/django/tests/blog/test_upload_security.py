from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from wagtail.documents.fields import WagtailDocumentField
from wagtail.images import get_image_model
from wagtail.images.fields import WagtailImageField
from wagtail.images.forms import get_image_form

pytestmark = pytest.mark.django_db

METADATA_SENTINEL = "metadata-must-not-survive"


def jpeg_upload(*, name="safe.jpg", metadata=True):
    image = Image.new("RGB", (24, 16), color="navy")
    exif = Image.Exif()
    if metadata:
        exif[0x013B] = METADATA_SENTINEL
    content = BytesIO()
    image.save(content, format="JPEG", exif=exif)
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/jpeg")


def test_upload_policy_is_explicit_and_bounded(settings):
    assert settings.WAGTAILIMAGES_EXTENSIONS == ["jpg", "jpeg", "png", "webp"]
    assert settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE == 8 * 1024 * 1024
    assert settings.WAGTAILIMAGES_MAX_IMAGE_PIXELS == 40_000_000
    assert settings.WAGTAILDOCS_EXTENSIONS == ["pdf"]
    assert settings.WAGTAILDOCS_MAX_UPLOAD_SIZE == 10 * 1024 * 1024


def test_image_form_reencodes_original_without_exif_or_metadata_sentinel():
    form_class = get_image_form(get_image_model())
    form = form_class(
        data={"title": "Sanitized upload"},
        files={"file": jpeg_upload()},
    )

    assert form.is_valid(), form.errors
    sanitized = form.cleaned_data["file"]
    payload = sanitized.read()
    assert METADATA_SENTINEL.encode() not in payload
    with Image.open(BytesIO(payload)) as image:
        assert not image.getexif()
        assert METADATA_SENTINEL not in repr(image.info)


def test_image_field_rejects_extension_content_mismatch():
    with pytest.raises(ValidationError, match="does not match"):
        WagtailImageField().clean(jpeg_upload(name="spoofed.png"))


@override_settings(WAGTAILIMAGES_MAX_UPLOAD_SIZE=1)
def test_image_field_enforces_size_limit():
    with pytest.raises(ValidationError, match="too big"):
        WagtailImageField().clean(jpeg_upload(metadata=False))


@override_settings(WAGTAILDOCS_MAX_UPLOAD_SIZE=1)
def test_document_field_enforces_size_limit():
    upload = SimpleUploadedFile("document.pdf", b"%PDF-1.7\nbounded")
    with pytest.raises(ValidationError, match="too big"):
        WagtailDocumentField().clean(upload)
