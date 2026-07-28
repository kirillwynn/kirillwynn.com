import warnings
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps
from wagtail.images.fields import WagtailImageField
from wagtail.images.forms import BaseImageForm

_FORMATS = {
    "JPEG": ("JPEG", "image/jpeg", {"optimize": True, "quality": 90}),
    "PNG": ("PNG", "image/png", {"optimize": True}),
    "WEBP": ("WEBP", "image/webp", {"method": 6, "quality": 90}),
}
STABLE_IMAGE_ERROR = "The image could not be decoded and sanitized."


class StableWagtailImageField(WagtailImageField):
    """Normalize Willow/Pillow failures from every field validation phase."""

    def to_python(self, data):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", UserWarning)
                return super().to_python(data)
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(STABLE_IMAGE_ERROR) from error


class MetadataStrippingImageForm(BaseImageForm):
    """Re-encode accepted uploads so public originals contain no source metadata."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "file" not in self.fields:
            return
        original = self.fields["file"]
        self.fields["file"] = StableWagtailImageField(
            disabled=original.disabled,
            help_text=original.help_text,
            label=original.label,
            required=original.required,
            widget=original.widget,
        )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        try:
            uploaded.seek(0)
            with warnings.catch_warnings():
                # Pillow reports some malformed EXIF as warnings and others as
                # parsing exceptions. Both are rejected at the same boundary.
                warnings.simplefilter("error", UserWarning)
                with Image.open(uploaded) as source:
                    if getattr(source, "is_animated", False):
                        raise ValidationError("Animated images are not accepted.")
                    image_format = source.format
                    if image_format not in _FORMATS:
                        raise ValidationError("This image format cannot be sanitized.")
                    source.getexif()
                    image = ImageOps.exif_transpose(source)
                    image.load()

            output_format, content_type, save_options = _FORMATS[image_format]
            if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            sanitized = BytesIO()
            image.save(sanitized, format=output_format, **save_options)
            payload = sanitized.getvalue()
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(STABLE_IMAGE_ERROR) from error

        if len(payload) > settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE:
            raise ValidationError("The sanitized image exceeds the upload size limit.")

        suffix = Path(uploaded.name).suffix.lower()
        filename = f"{Path(uploaded.name).stem}{suffix}"
        return SimpleUploadedFile(filename, payload, content_type=content_type)
