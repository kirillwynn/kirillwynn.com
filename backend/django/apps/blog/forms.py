from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps
from wagtail.images.forms import BaseImageForm

_FORMATS = {
    "JPEG": ("JPEG", "image/jpeg", {"optimize": True, "quality": 90}),
    "PNG": ("PNG", "image/png", {"optimize": True}),
    "WEBP": ("WEBP", "image/webp", {"method": 6, "quality": 90}),
}


class MetadataStrippingImageForm(BaseImageForm):
    """Re-encode accepted uploads so public originals contain no source metadata."""

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        uploaded.seek(0)
        with Image.open(uploaded) as source:
            if getattr(source, "is_animated", False):
                raise ValidationError("Animated images are not accepted.")
            image_format = source.format
            if image_format not in _FORMATS:
                raise ValidationError("This image format cannot be sanitized.")
            image = ImageOps.exif_transpose(source)
            image.load()

        output_format, content_type, save_options = _FORMATS[image_format]
        if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        sanitized = BytesIO()
        image.save(sanitized, format=output_format, **save_options)
        payload = sanitized.getvalue()
        if len(payload) > settings.WAGTAILIMAGES_MAX_UPLOAD_SIZE:
            raise ValidationError("The sanitized image exceeds the upload size limit.")

        suffix = Path(uploaded.name).suffix.lower()
        filename = f"{Path(uploaded.name).stem}{suffix}"
        return SimpleUploadedFile(filename, payload, content_type=content_type)
