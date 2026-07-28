from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from wagtail.documents import get_document_model
from wagtail.documents.fields import WagtailDocumentField
from wagtail.documents.forms import get_document_form
from wagtail.images import get_image_model
from wagtail.images.fields import WagtailImageField
from wagtail.images.forms import get_image_form, get_image_multi_form

pytestmark = pytest.mark.django_db

METADATA_SENTINEL = "metadata-must-not-survive"
STABLE_IMAGE_ERROR = "The image could not be decoded and sanitized."


def image_upload(
    image_format="JPEG",
    *,
    name=None,
    metadata=True,
    size=(24, 16),
):
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
    image = Image.new("RGB", size, color="navy")
    content = BytesIO()
    save_options = {}
    if metadata:
        exif = Image.Exif()
        exif[0x013B] = METADATA_SENTINEL
        save_options["exif"] = exif
    if image_format == "PNG":
        save_options["pnginfo"] = None
    image.save(content, format=image_format, **save_options)
    return SimpleUploadedFile(
        name or f"safe.{extension}",
        content.getvalue(),
        content_type={"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image_format],
    )


def malformed_exif_upload(image_format):
    upload = image_upload(image_format, metadata=True)
    payload = bytearray(upload.read())
    if image_format == "JPEG":
        marker = payload.find(b"Exif\x00\x00")
        assert marker >= 0
        tiff_header = marker + 6
    else:
        tiff_header = payload.find(b"MM\x00*")
        assert tiff_header >= 0
    payload[tiff_header : tiff_header + 8] = b"MM\x00*\xff\xff\xff\xff"
    return SimpleUploadedFile(upload.name, payload, content_type=upload.content_type)


def animated_webp_upload():
    content = BytesIO()
    frames = [
        Image.new("RGB", (8, 8), color="navy"),
        Image.new("RGB", (8, 8), color="orange"),
    ]
    frames[0].save(
        content,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    return SimpleUploadedFile("animated.webp", content.getvalue(), content_type="image/webp")


def image_form(upload):
    return get_image_form(get_image_model())(
        data={"title": "Sanitized upload"},
        files={"file": upload},
    )


def test_multi_upload_edit_form_keeps_its_fileless_boundary():
    form_class = get_image_multi_form(get_image_model())

    assert "file" not in form_class().fields


def test_upload_policy_is_explicit_and_bounded(settings):
    assert settings.WAGTAILIMAGES_EXTENSIONS == ["jpg", "jpeg", "png", "webp"]
    assert settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE == 8 * 1024 * 1024
    assert settings.WAGTAILIMAGES_MAX_IMAGE_PIXELS == 40_000_000
    assert settings.WAGTAILDOCS_EXTENSIONS == ["pdf"]
    assert settings.WAGTAILDOCS_MAX_UPLOAD_SIZE == 10 * 1024 * 1024


@pytest.mark.parametrize(
    ("image_format", "extension", "content_type"),
    [
        ("JPEG", ".jpg", "image/jpeg"),
        ("PNG", ".png", "image/png"),
        ("WEBP", ".webp", "image/webp"),
    ],
)
def test_image_form_preserves_format_extension_dimensions_and_strips_metadata(
    image_format,
    extension,
    content_type,
):
    form = image_form(image_upload(image_format))

    assert form.is_valid(), form.errors
    sanitized = form.cleaned_data["file"]
    payload = sanitized.read()
    assert sanitized.name.endswith(extension)
    assert sanitized.content_type == content_type
    assert METADATA_SENTINEL.encode() not in payload
    with Image.open(BytesIO(payload)) as image:
        assert image.format == image_format
        assert image.size == (24, 16)
        assert not image.getexif()
        assert METADATA_SENTINEL not in repr(image.info)


@pytest.mark.parametrize("image_format", ["JPEG", "WEBP"])
def test_malformed_exif_is_a_stable_form_validation_error(image_format):
    form = image_form(malformed_exif_upload(image_format))

    assert not form.is_valid()
    assert STABLE_IMAGE_ERROR in form.errors["file"]


@pytest.mark.parametrize(
    "payload",
    [
        SimpleUploadedFile("truncated.jpg", b"\xff\xd8\xff\xe1", content_type="image/jpeg"),
        SimpleUploadedFile("corrupt.png", b"\x89PNG\r\n\x1a\ncorrupt", content_type="image/png"),
        SimpleUploadedFile(
            "corrupt.webp", b"RIFF\x10\x00\x00\x00WEBPcorrupt", content_type="image/webp"
        ),
    ],
)
def test_truncated_or_corrupt_images_are_validation_errors(payload):
    form = image_form(payload)

    assert not form.is_valid()
    assert "file" in form.errors


@pytest.mark.parametrize(
    ("target", "side_effect"),
    [
        ("apps.blog.forms.ImageOps.exif_transpose", SyntaxError("bad EXIF")),
        ("apps.blog.forms.Image.Image.load", OSError("decode failed")),
        ("apps.blog.forms.Image.Image.save", OSError("encode failed")),
    ],
)
def test_pillow_exif_decode_and_encode_failures_share_stable_error(target, side_effect):
    upload = image_upload("JPEG", metadata=False)
    with patch(target, side_effect=side_effect):
        form = image_form(upload)
        assert not form.is_valid()

    assert STABLE_IMAGE_ERROR in form.errors["file"]


def test_image_field_rejects_extension_content_mismatch():
    with pytest.raises(ValidationError, match="does not match"):
        WagtailImageField().clean(image_upload("JPEG", name="spoofed.png"))


@override_settings(WAGTAILIMAGES_MAX_UPLOAD_SIZE=1)
def test_image_field_enforces_size_limit():
    with pytest.raises(ValidationError, match="too big"):
        WagtailImageField().clean(image_upload("JPEG", metadata=False))


@override_settings(WAGTAILIMAGES_MAX_IMAGE_PIXELS=1)
def test_image_field_enforces_pixel_limit():
    with pytest.raises(ValidationError, match="too many pixels"):
        WagtailImageField().clean(image_upload("PNG", metadata=False, size=(2, 2)))


def test_image_form_rejects_animation():
    form = image_form(animated_webp_upload())

    assert not form.is_valid()
    assert "Animated images are not accepted." in form.errors["file"]


def test_wagtail_admin_upload_boundary_returns_validation_error(
    client,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    admin = get_user_model().objects.create_superuser(
        username="upload-admin",
        email="upload-admin@example.com",
        password="password",
    )
    client.force_login(admin)

    response = client.post(
        reverse("wagtailimages:add"),
        data={
            "title": "Malformed upload",
            "file": malformed_exif_upload("WEBP"),
        },
    )

    assert response.status_code == 200
    assert STABLE_IMAGE_ERROR in response.content.decode()
    assert not get_image_model().objects.filter(title="Malformed upload").exists()


@pytest.mark.parametrize("image_format", ["JPEG", "PNG", "WEBP"])
def test_wagtail_admin_upload_boundary_accepts_sanitized_formats(
    client,
    image_format,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = tmp_path
    admin = get_user_model().objects.create_superuser(
        username=f"upload-admin-{image_format.lower()}",
        email=f"{image_format.lower()}@example.com",
        password="password",
    )
    client.force_login(admin)

    response = client.post(
        reverse("wagtailimages:add"),
        data={
            "title": f"Valid {image_format}",
            "file": image_upload(image_format),
        },
    )

    assert response.status_code == 302
    uploaded = get_image_model().objects.get(title=f"Valid {image_format}")
    with uploaded.file.open("rb") as stored:
        with Image.open(stored) as image:
            assert image.format == image_format
            assert not image.getexif()


def test_document_field_rejects_non_pdf_extension():
    form = get_document_form(get_document_model())(
        data={"title": "Wrong extension"},
        files={
            "file": SimpleUploadedFile(
                "document.txt",
                b"%PDF-1.7\nextension mismatch",
            )
        },
    )

    assert not form.is_valid()
    assert "file" in form.errors


@override_settings(WAGTAILDOCS_MAX_UPLOAD_SIZE=1)
def test_document_field_enforces_size_limit():
    upload = SimpleUploadedFile("document.pdf", b"%PDF-1.7\nbounded")
    with pytest.raises(ValidationError, match="too big"):
        WagtailDocumentField().clean(upload)


def test_document_boundary_is_extension_only_and_does_not_parse_pdf_content():
    upload = SimpleUploadedFile("document.pdf", b"not actually a PDF")
    form = get_document_form(get_document_model())(
        data={"title": "Extension-only PDF"},
        files={"file": upload},
    )

    assert form.is_valid(), form.errors
