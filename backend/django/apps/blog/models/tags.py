from django.db import models
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase


class BlogPostTag(TaggedItemBase):
    content_object = ParentalKey(
        "blog.BlogPostPage",
        on_delete=models.CASCADE,
        related_name="tagged_items",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_object", "tag"],
                name="unique_blog_post_tag",
            )
        ]
