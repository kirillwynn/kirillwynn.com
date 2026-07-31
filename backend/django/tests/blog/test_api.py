import json
from datetime import timedelta

import pytest
from django.core import signing
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import PageViewRestriction

from apps.blog.api.serializers import API_VERSION, IMAGE_RENDITION_SPECS, _absolute_url
from apps.blog.models import BlogPostPage, PreviewSnapshot
from apps.blog.services.preview import PREVIEW_SIGNING_SALT, _credential_digest
from tests.blog.test_blocks import all_block_values

pytestmark = pytest.mark.django_db


def publish(page):
    page.save_revision().publish()
    return BlogPostPage.objects.get(pk=page.pk)


def make_post(blog_index, *, number, live=True):
    post = BlogPostPage(
        title=f"Post {number}",
        slug=f"post-{number}",
        excerpt=f"Excerpt {number}",
        body=[("rich_text", f"<p>Body {number}</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    return publish(post) if live else post


def issue_headless_preview(page):
    draft = page.save_revision().as_object()
    response = draft.make_preview_request(preview_mode="headless")
    return response, response.cookies["kw_preview_credential"].value


def test_list_contract_is_paginated_compact_and_exact(blog_post):
    blog_post.title = "Published post"
    blog_post.slug = "published-post"
    blog_post.tags.add("Wagtail", "django")
    published = publish(blog_post)

    response = APIClient().get(reverse("blog_api:post-list"))

    assert response.status_code == 200
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 1
    assert response.data["next"] is None
    assert response.data["previous"] is None
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert set(result) == {
        "api_version",
        "id",
        "slug",
        "title",
        "excerpt",
        "published_at",
        "updated_at",
        "original_published_at",
        "display_published_at",
        "tags",
        "canonical_path",
        "canonical_url",
        "seo",
        "open_graph",
        "lead_image",
    }
    assert result["api_version"] == API_VERSION
    assert result["id"] == published.pk
    assert result["slug"] == "published-post"
    assert result["tags"] == [
        {"name": "django", "slug": "django"},
        {"name": "Wagtail", "slug": "wagtail"},
    ]
    assert result["canonical_path"] == "/posts/published-post"
    assert result["canonical_url"] == "http://localhost:3000/posts/published-post"
    assert result["seo"] == {
        "title": "Published post",
        "description": "A concise draft excerpt.",
    }
    assert result["open_graph"]["title"] == "Published post"
    assert result["open_graph"]["description"] == "A concise draft excerpt."
    assert result["lead_image"] is None
    assert "body" not in result


def test_detail_contract_has_fallbacks_and_serialized_body(blog_post):
    blog_post.title = "Contract post"
    blog_post.slug = "contract-post"
    blog_post.seo_title = "SEO title"
    blog_post.search_description = "SEO description"
    blog_post.open_graph_title = "OG title"
    blog_post.open_graph_description = "OG description"
    blog_post.canonical_url = "https://canonical.example/post"
    blog_post.tags.add("Zulu", "Alpha")
    published = publish(blog_post)

    response = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))

    assert response.status_code == 200
    assert set(response.data) == {
        "api_version",
        "id",
        "slug",
        "title",
        "excerpt",
        "published_at",
        "updated_at",
        "original_published_at",
        "display_published_at",
        "tags",
        "canonical_path",
        "canonical_url",
        "seo",
        "open_graph",
        "body",
    }
    assert response.data["api_version"] == "1.0"
    assert response.data["published_at"].endswith("Z")
    assert response.data["updated_at"].endswith("Z")
    assert response.data["canonical_path"] == "/posts/contract-post"
    assert response.data["canonical_url"] == "https://canonical.example/post"
    assert response.data["tags"] == [
        {"name": "Alpha", "slug": "alpha"},
        {"name": "Zulu", "slug": "zulu"},
    ]
    assert response.data["seo"] == {
        "title": "SEO title",
        "description": "SEO description",
    }
    assert response.data["open_graph"] == {
        "title": "OG title",
        "description": "OG description",
        "image": None,
    }
    assert response.data["body"][0]["type"] == "rich_text"
    assert response.data["body"][0]["value"] == {"html": "<p>Draft body.</p>"}


def test_all_thirteen_streamfield_blocks_have_exact_discriminated_values(blog_post, wagtail_image):
    blog_post.body = all_block_values(wagtail_image)
    published = publish(blog_post)

    body = (
        APIClient()
        .get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))
        .data["body"]
    )

    assert [block["type"] for block in body] == [
        "rich_text",
        "heading",
        "image",
        "gallery",
        "quote",
        "bulleted_list",
        "numbered_list",
        "checklist",
        "inline_code",
        "code_block",
        "table",
        "horizontal_divider",
        "link",
    ]
    assert all(set(block) == {"id", "type", "value"} for block in body)
    assert all(block["id"] for block in body)
    assert body[0]["value"] == {"html": "<p><strong>Rich text</strong></p>"}
    assert body[1]["value"] == {"level": "h2", "text": "Section"}
    assert set(body[2]["value"]) == {
        "id",
        "title",
        "alt",
        "decorative",
        "width",
        "height",
        "renditions",
    }
    assert body[3]["value"]["images"][0]["alt"] == "A descriptive alt"
    assert body[4]["value"] == {
        "text": "A useful quotation.",
        "attribution": "Author",
    }
    assert body[5]["value"] == {"items": ["First", "Second"]}
    assert body[6]["value"] == {"items": ["First", "Second"]}
    assert body[7]["value"] == {
        "items": [
            {"text": "Done", "checked": True},
            {"text": "Pending", "checked": False},
        ]
    }
    assert body[8]["value"] == {"code": "print(value)"}
    assert body[9]["value"] == {
        "language": "python",
        "code": "print('hello')",
    }
    assert body[10]["value"] == {
        "rows": [["Name", "Value"], ["answer", "42"]],
        "header": {"row": True, "column": False},
    }
    assert body[11]["value"] == {}
    assert body[12]["value"] == {
        "text": "Internal link",
        "kind": "internal",
        "href": "/",
        "target": {
            "id": body[12]["value"]["target"]["id"],
            "type": "wagtailcore.page",
            "slug": "root",
        },
    }


def test_internal_links_use_frontend_routes_in_blocks_and_rich_text(blog_index, blog_post):
    target = make_post(blog_index, number="target")
    blog_post.body = [
        (
            "rich_text",
            f'<p><a linktype="page" id="{target.pk}">Rich target</a></p>',
        ),
        (
            "link",
            {
                "text": "Index target",
                "internal_page": blog_index,
                "external_url": "",
            },
        ),
        (
            "link",
            {
                "text": "Post target",
                "internal_page": target,
                "external_url": "",
            },
        ),
    ]
    published = publish(blog_post)

    body = (
        APIClient()
        .get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))
        .data["body"]
    )

    assert body[0]["value"]["html"] == (f'<p><a href="/posts/{target.slug}">Rich target</a></p>')
    assert body[1]["value"]["href"] == "/"
    assert body[2]["value"]["href"] == f"/posts/{target.slug}"


def test_image_renditions_and_open_graph_fallback_are_structured(blog_post, wagtail_image):
    blog_post.body = [
        {
            "type": "image",
            "value": {
                "image": wagtail_image.pk,
                "decorative": False,
                "alt_text": "Contextual lead alt",
            },
        }
    ]
    published = publish(blog_post)

    data = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug})).data
    image = data["open_graph"]["image"]

    assert image["id"] == wagtail_image.pk
    assert image["title"] == "Test image"
    assert image["alt"] == "Contextual lead alt"
    assert image["decorative"] is False
    assert image["width"] == 2
    assert image["height"] == 2
    assert set(image["renditions"]) == set(IMAGE_RENDITION_SPECS)
    assert all(
        set(rendition) == {"url", "width", "height"} for rendition in image["renditions"].values()
    )
    assert all(
        rendition["url"].startswith("http://localhost:3000/media/")
        for rendition in image["renditions"].values()
    )


@override_settings(PUBLIC_SITE_URL="https://kirillwynn.com")
def test_absolute_storage_urls_pass_through_unchanged():
    cdn_url = "https://cdn.example.com/media/rendition.jpg"

    assert _absolute_url(cdn_url) == cdn_url
    assert _absolute_url("/media/rendition.jpg") == ("https://kirillwynn.com/media/rendition.jpg")


def test_pagination_enforces_maximum_page_size(blog_index):
    for number in range(51):
        make_post(blog_index, number=number)

    response = APIClient().get(reverse("blog_api:post-list"), {"page_size": 999})

    assert response.status_code == 200
    assert response.data["count"] == 51
    assert len(response.data["results"]) == 50
    assert response.data["next"] == "/api/v1/posts/?page=2&page_size=999"


def test_unicode_slug_detail_canonical_and_internal_link(blog_index, blog_post):
    target = make_post(blog_index, number="target")
    target.slug = "привет-мир"
    target = publish(target)
    blog_post.body = [
        (
            "rich_text",
            f'<p><a linktype="page" id="{target.pk}">Русская публикация</a></p>',
        ),
        (
            "link",
            {
                "text": "Русская публикация",
                "internal_page": target,
                "external_url": "",
            },
        ),
    ]
    published = publish(blog_post)

    response = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": target.slug}))
    source = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))

    assert response.status_code == 200
    assert response.data["slug"] == "привет-мир"
    assert response.data["canonical_path"] == "/posts/привет-мир"
    assert response.data["canonical_url"] == (
        "http://localhost:3000/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80"
    )
    assert source.data["body"][0]["value"]["html"] == (
        '<p><a href="/posts/привет-мир">Русская публикация</a></p>'
    )
    assert source.data["body"][1]["value"]["href"] == "/posts/привет-мир"


@override_settings(
    PUBLIC_SITE_URL="https://kirillwynn.com",
    ALLOWED_HOSTS=["django"],
)
def test_frontend_urls_never_leak_internal_django_origin(blog_index, blog_post, wagtail_image):
    for number in range(10):
        make_post(blog_index, number=f"pagination-{number}")
    blog_post.title = "Public origin"
    blog_post.slug = "привет-мир"
    blog_post.body = [
        {
            "type": "image",
            "value": {
                "image": wagtail_image.pk,
                "decorative": False,
                "alt_text": "Public image",
            },
        }
    ]
    published = publish(blog_post)
    _, credential = issue_headless_preview(published)

    client = APIClient(HTTP_HOST="django:8000")
    detail = client.get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))
    listing = client.get(reverse("blog_api:post-list"))
    preview = client.post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert detail.status_code == listing.status_code == preview.status_code == 200
    assert detail.data["canonical_url"].startswith("https://kirillwynn.com/posts/")
    assert detail.data["open_graph"]["image"] is not None
    assert all(
        item["url"].startswith("https://kirillwynn.com/media/")
        for item in detail.data["open_graph"]["image"]["renditions"].values()
    )
    lead_image = next(
        item["lead_image"] for item in listing.data["results"] if item["id"] == published.pk
    )
    assert lead_image is not None
    assert listing.data["next"].startswith("/api/v1/posts/?")
    assert listing.data["previous"] is None
    assert preview.data["canonical_url"] == detail.data["canonical_url"]
    assert preview.data["open_graph"]["image"] == detail.data["open_graph"]["image"]

    serialized = json.dumps(
        {
            "detail": detail.data,
            "listing": listing.data,
            "preview": preview.data,
        }
    )
    assert "django:8000" not in serialized
    assert "localhost:8000" not in serialized
    assert "testserver" not in serialized


def test_public_visibility_policy_excludes_every_non_public_state(blog_index):
    now = timezone.now()
    live_post = make_post(blog_index, number="live")
    draft = make_post(blog_index, number="draft", live=False)
    unpublished = make_post(blog_index, number="unpublished")
    unpublished.unpublish()
    future = make_post(blog_index, number="future")
    BlogPostPage.objects.filter(pk=future.pk).update(go_live_at=now + timedelta(hours=1))
    expired = make_post(blog_index, number="expired")
    BlogPostPage.objects.filter(pk=expired.pk).update(expire_at=now - timedelta(seconds=1))
    private = make_post(blog_index, number="private")
    PageViewRestriction.objects.create(
        page=private,
        restriction_type=PageViewRestriction.PASSWORD,
        password="not-a-runtime-secret",
    )

    response = APIClient().get(reverse("blog_api:post-list"))
    slugs = {item["slug"] for item in response.data["results"]}

    assert slugs == {live_post.slug}
    for hidden in [draft, unpublished, future, expired, private]:
        detail = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": hidden.slug}))
        assert detail.status_code == 404
        assert detail.data == {"detail": "No BlogPostPage matches the given query."}


def test_public_detail_rejects_preview_credentials_and_never_exposes_preview(blog_post):
    published = publish(blog_post)
    blog_post.title = "Unpublished changed title"
    _, credential = issue_headless_preview(blog_post)

    public = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))
    rejected = APIClient().get(
        reverse("blog_api:post-detail", kwargs={"slug": published.slug}),
        {"credential": credential},
    )

    assert public.data["title"] == "Draft post"
    assert public.data["title"] != "Unpublished changed title"
    assert "preview" not in public.data
    assert rejected.status_code == 400


def test_headless_preview_is_bound_to_one_immutable_snapshot_and_no_store(blog_post):
    blog_post.title = "Snapshot one"
    response, credential = issue_headless_preview(blog_post)
    assert response.status_code == 302
    assert response["Location"] == "http://frontend.test/api/draft"
    assert "token" not in response["Location"]
    assert response.cookies["kw_preview_credential"]["httponly"]
    assert not response.cookies["kw_preview_credential"]["secure"]
    assert response["Cache-Control"] == "private, no-store"

    blog_post.title = "Snapshot two"
    blog_post.save_revision()
    resolved = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert resolved.status_code == 200
    assert resolved.data["title"] == "Snapshot one"
    assert resolved.data["canonical_path"] == f"/posts/{blog_post.slug}"
    assert resolved["Cache-Control"] == "private, no-store"
    assert resolved["Pragma"] == "no-cache"


@override_settings(PREVIEW_COOKIE_SECURE=True)
def test_production_preview_entry_cookie_is_secure_on_internal_http(blog_post):
    response, _ = issue_headless_preview(blog_post)

    assert response["Location"].startswith("http://")
    assert response.cookies["kw_preview_credential"]["secure"]


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_invalid_preview_credentials_are_indistinguishable(blog_post, mutation):
    _, credential = issue_headless_preview(blog_post)
    if mutation == "missing":
        credential = "x" * 80
    else:
        credential = credential[:-1] + ("a" if credential[-1] != "a" else "b")

    response = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Preview is unavailable."}


def test_expired_preview_credential_is_rejected(blog_post, monkeypatch):
    now = 1_800_000_000
    monkeypatch.setattr(signing.time, "time", lambda: now)
    _, credential = issue_headless_preview(blog_post)
    monkeypatch.setattr(signing.time, "time", lambda: now + 601)

    response = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert response.status_code == 404
    assert response.data == {"detail": "Preview is unavailable."}


def test_preview_rejects_snapshot_for_another_page(blog_index, blog_post):
    _, credential = issue_headless_preview(blog_post)
    PreviewSnapshot.objects.filter(credential_digest=_credential_digest(credential)).update(
        page_id=blog_index.pk
    )

    response = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert response.status_code == 404


def test_preview_rejects_snapshot_for_another_content_type(blog_index):
    credential = signing.TimestampSigner(salt=PREVIEW_SIGNING_SALT).sign("opaque-value")
    PreviewSnapshot.objects.create(
        credential_digest=_credential_digest(credential),
        content_type=blog_index.content_type,
        page_id=blog_index.pk,
        content_json=blog_index.to_json(),
    )

    response = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )

    assert response.status_code == 404


def test_public_endpoints_are_anonymous_and_read_only(blog_post):
    published = publish(blog_post)
    client = APIClient()

    assert client.get(reverse("blog_api:post-list")).status_code == 200
    assert (
        client.get(reverse("blog_api:post-detail", kwargs={"slug": published.slug})).status_code
        == 200
    )
    assert client.post(reverse("blog_api:post-list"), {}, format="json").status_code == 405
    assert (
        client.post(
            reverse("blog_api:post-detail", kwargs={"slug": published.slug}),
            {},
            format="json",
        ).status_code
        == 405
    )


def test_list_image_loading_does_not_grow_per_post(blog_index, wagtail_image):
    for number in range(5):
        post = BlogPostPage(
            title=f"Image post {number}",
            slug=f"image-post-{number}",
            excerpt="Image query contract.",
            body=[
                {
                    "type": "image",
                    "value": {
                        "image": wagtail_image.pk,
                        "decorative": False,
                        "alt_text": f"Context {number}",
                    },
                }
            ],
            live=False,
        )
        blog_index.add_child(instance=post)
        publish(post)
    wagtail_image.get_renditions(*IMAGE_RENDITION_SPECS.values())

    with CaptureQueriesContext(connection) as one_post_queries:
        one = APIClient().get(reverse("blog_api:post-list"), {"page_size": 1})
    with CaptureQueriesContext(connection) as five_post_queries:
        five = APIClient().get(reverse("blog_api:post-list"), {"page_size": 5})

    assert one.status_code == five.status_code == 200
    assert len(five.data["results"]) == 5
    assert len(five_post_queries) <= len(one_post_queries) + 1, [
        query["sql"] for query in five_post_queries.captured_queries
    ]
