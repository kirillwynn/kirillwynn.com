from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.encoding import iri_to_uri
from modelcluster.contrib.taggit import ClusterTaggableManager
from wagtail.admin.panels import (
    FieldPanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
    TitleFieldPanel,
)
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail_headless_preview.models import HeadlessPreviewMixin

from apps.blog.blocks import BlogBodyBlock
from apps.blog.editor_forms import BlogPostPageForm
from apps.blog.editor_panels import ReadOnlyPropertyPanel

SEARCH_BOOST_TITLE = 10
SEARCH_BOOST_EXCERPT = 7
SEARCH_BOOST_BODY = 4
SEARCH_BOOST_TAGS = 2


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
    original_published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Original publication date",
        help_text=(
            "For archived material, enter when it was first published elsewhere. "
            "Leave this blank for new material. Wagtail scheduling is controlled "
            "separately in Publishing schedule."
        ),
    )
    notify_subscribers_on_first_publication = models.BooleanField(
        default=True,
        verbose_name="Notify subscribers on first publication",
        help_text=(
            "Keep this selected for a new post. Clear it for an archive import. "
            "The choice is locked when the post first becomes public."
        ),
    )
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

    base_form_class = BlogPostPageForm

    writing_panels = [
        TitleFieldPanel(
            "title",
            classname="editorial-title-panel",
            attrs={"data-editorial-field": "title"},
        ),
        FieldPanel(
            "excerpt",
            classname="editorial-excerpt-panel",
            attrs={"data-editorial-field": "excerpt"},
        ),
        FieldPanel(
            "body",
            classname="editorial-body-panel",
            attrs={"data-editorial-field": "body"},
        ),
    ]
    publication_panels = [
        MultiFieldPanel(
            [
                FieldPanel("original_published_at"),
                FieldPanel("notify_subscribers_on_first_publication"),
                ReadOnlyPropertyPanel(
                    "newsletter_status",
                    heading="Newsletter decision",
                    help_text=(
                        "This durable status is separate from revisions and cannot be "
                        "re-armed by restoring older content."
                    ),
                    read_only=True,
                ),
            ],
            heading="Publication intent",
            classname="editorial-publication-intent",
        ),
        FieldPanel(
            "tags",
            heading="Tags",
            help_text="Optional labels used by Feed filters and search.",
        ),
        *Page.settings_panels,
    ]
    sharing_panels = [
        MultiFieldPanel(
            [
                FieldPanel("slug"),
                FieldPanel("seo_title"),
                FieldPanel("search_description"),
            ],
            heading="Search and URL",
        ),
        MultiFieldPanel(
            [
                FieldPanel("canonical_url"),
                FieldPanel("open_graph_image"),
                FieldPanel("open_graph_title"),
                FieldPanel("open_graph_description"),
            ],
            heading="Canonical and Open Graph sharing",
        ),
    ]
    edit_handler = TabbedInterface(
        [
            ObjectList(writing_panels, heading="Write"),
            ObjectList(publication_panels, heading="Publish"),
            ObjectList(sharing_panels, heading="SEO & sharing"),
        ],
        base_form_class=BlogPostPageForm,
    )

    # ModelSearch de-duplicates fields by type and name, with the later
    # definition winning. Keeping Page.search_fields intact also preserves all
    # Wagtail core filter/autocomplete fields and its system-check contract.
    search_fields = Page.search_fields + [
        index.SearchField("title", boost=SEARCH_BOOST_TITLE),
        index.SearchField("excerpt", boost=SEARCH_BOOST_EXCERPT),
        index.SearchField("body", boost=SEARCH_BOOST_BODY),
        index.FilterField("go_live_at"),
        index.FilterField("expire_at"),
        index.RelatedFields(
            "tags",
            [index.FilterField("slug")],
        ),
        index.SearchField("searchable_tag_names", boost=SEARCH_BOOST_TAGS),
    ]

    def searchable_tag_names(self):
        """Flatten the related ClusterTaggableManager into one tag-only field."""

        return "\n".join(self.tags.order_by("slug", "name").values_list("name", flat=True))

    @property
    def display_published_at(self):
        """Return the editorial display date without changing Wagtail state."""

        return self.original_published_at or self.first_published_at

    @property
    def newsletter_status(self):
        if not self.pk:
            return "Pending — the choice will be locked when this post first becomes public."

        from apps.subscriptions.models import PostPublicationEmailDecision

        try:
            decision = self.publication_email_decision
        except PostPublicationEmailDecision.DoesNotExist:
            return "Pending — the choice will be locked when this post first becomes public."

        if decision.state == PostPublicationEmailDecision.State.QUEUED:
            return "Queued — one publication notification was created and the choice is locked."
        if decision.state == PostPublicationEmailDecision.State.SUPPRESSED:
            return (
                "Suppressed — no publication notification was created, and restoring an "
                "older revision cannot enable it."
            )
        return "Pending — the choice will be locked when this post first becomes public."

    @property
    def resolved_canonical_url(self):
        path = iri_to_uri(f"/posts/{self.slug}")
        return self.canonical_url or f"{settings.PUBLIC_SITE_URL}{path}"

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
            secure=settings.PREVIEW_COOKIE_SECURE,
            samesite="Lax",
            path="/api/draft",
        )
        response["Cache-Control"] = "private, no-store"
        return response

    def clean(self):
        super().clean()
        original_published_at = self.original_published_at
        if original_published_at is not None:
            if timezone.is_naive(original_published_at):
                raise ValidationError(
                    {"original_published_at": ("Enter a date and time with a valid time zone.")}
                )
            if original_published_at > timezone.now():
                raise ValidationError(
                    {"original_published_at": "Original publication date cannot be in the future."}
                )

            site_first_published_at = self.first_published_at
            if self.pk:
                persisted_page = (
                    Page.objects.filter(pk=self.pk)
                    .values_list("first_published_at", flat=True)
                    .first()
                )
                if persisted_page is not None:
                    site_first_published_at = persisted_page
            if (
                site_first_published_at is not None
                and original_published_at > site_first_published_at
            ):
                raise ValidationError(
                    {
                        "original_published_at": (
                            "For an already published post, the original date cannot be "
                            "later than its first publication on this site."
                        )
                    }
                )

        try:
            self.body.stream_block.clean(self.body)
        except ValidationError as error:
            raise ValidationError({"body": error}) from error

    class Meta:
        verbose_name = "Blog post"
