import uuid

from django.contrib.contenttypes.models import ContentType
from django.db import models


class PreviewSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential_digest = models.CharField(max_length=64, unique=True, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    page_id = models.PositiveBigIntegerField()
    content_json = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="blog_preview_created_idx"),
            models.Index(
                fields=["content_type", "page_id"],
                name="blog_preview_page_idx",
            ),
        ]
