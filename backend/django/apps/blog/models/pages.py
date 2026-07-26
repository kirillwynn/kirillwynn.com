from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models, transaction
from modelcluster.contrib.taggit import ClusterTaggableManager
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail_headless_preview.models import HeadlessPreviewMixin

from apps.blog.blocks import BlogBodyBlock


class BlogIndexPage(Page):
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["blog.BlogPostPage"]
    preview_modes = []

    @classmethod
    def can_exist_under(cls, parent):
        return parent.is_root() and super().can_exist_under(parent)

    class Meta:
        verbose_name = "Blog index"


class BlogPostPage(HeadlessPreviewMixin, Page):
    parent_page_types = ["blog.BlogIndexPage"]
    subpage_types = []
    preview_modes = [
        ("headless", "Headless frontend"),
        ("backend", "Backend fallback"),
    ]

    excerpt = models.CharField(
        max_length=320,
        help_text="Required plain-text summary used in feeds and metadata fallbacks.",
    )
    body = StreamField(BlogBodyBlock(), use_json_field=True)
    tags = ClusterTaggableManager(through="blog.BlogPostTag", blank=True)
    canonical_url = models.URLField(
        blank=True,
        max_length=2_048,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Optional absolute canonical URL. Defaults to this page's public URL.",
    )
    open_graph_image = models.ForeignKey(
        "wagtailimages.Image",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Optional social image. Defaults to the first body or gallery image.",
    )
    open_graph_title = models.CharField(
        blank=True,
        max_length=70,
        help_text="Defaults to SEO title, then page title.",
    )
    open_graph_description = models.CharField(
        blank=True,
        max_length=200,
        help_text="Defaults to search description, then excerpt.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("excerpt"),
        FieldPanel("body"),
        FieldPanel("tags"),
    ]
    promote_panels = Page.promote_panels + [
        MultiFieldPanel(
            [
                FieldPanel("canonical_url"),
                FieldPanel("open_graph_image"),
                FieldPanel("open_graph_title"),
                FieldPanel("open_graph_description"),
            ],
            heading="Canonical and Open Graph",
        )
    ]

    search_fields = Page.search_fields + [
        index.SearchField("excerpt", boost=1.5),
        index.SearchField("body"),
        index.RelatedFields("tags", [index.SearchField("name")]),
    ]

    @property
    def resolved_canonical_url(self):
        return self.canonical_url or self.full_url

    @property
    def resolved_open_graph_title(self):
        return self.open_graph_title or self.seo_title or self.title

    @property
    def resolved_open_graph_description(self):
        return self.open_graph_description or self.search_description or self.excerpt

    @property
    def resolved_open_graph_image(self):
        if self.open_graph_image:
            return self.open_graph_image

        for block in self.body:
            if block.block_type == "image":
                return block.value
            if block.block_type == "gallery" and block.value:
                return block.value[0]

        return None

    def get_preview_template(self, request, mode_name):
        return "blog/blog_post_page_preview.html"

    @transaction.atomic
    def publish(self, *args, **kwargs):
        return super().publish(*args, **kwargs)

    @transaction.atomic
    def unpublish(self, *args, **kwargs):
        return super().unpublish(*args, **kwargs)

    def get_preview_url(self, request, token):
        from apps.blog.services.preview import issue_preview_credential

        self._issued_preview_credential = issue_preview_credential(
            package_token=token,
            expected_page=self,
        )
        return self.get_client_root_url(request)

    def serve_preview(self, request, preview_mode):
        if preview_mode == "backend":
            return Page.serve_preview(self, request, preview_mode)

        response = super().serve_preview(request, preview_mode)
        response.set_cookie(
            settings.PREVIEW_ENTRY_COOKIE_NAME,
            self._issued_preview_credential,
            max_age=settings.PREVIEW_TOKEN_TTL_SECONDS,
            httponly=True,
            secure=request.is_secure(),
            samesite="Lax",
            path="/api/draft",
        )
        response["Cache-Control"] = "private, no-store"
        return response

    def clean(self):
        super().clean()
        try:
            self.body.stream_block.clean(self.body)
        except ValidationError as error:
            raise ValidationError({"body": error}) from error

    class Meta:
        verbose_name = "Blog post"
