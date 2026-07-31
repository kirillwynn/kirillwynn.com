from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import PageViewRestriction
from wagtail.search import index

from apps.blog.api.query import MAX_QUERY_CODE_POINTS
from apps.blog.models import BlogPostPage
from apps.blog.models.pages import (
    SEARCH_BOOST_BODY,
    SEARCH_BOOST_EXCERPT,
    SEARCH_BOOST_TAGS,
    SEARCH_BOOST_TITLE,
)
from apps.blog.services.visibility import public_blog_posts

pytestmark = pytest.mark.django_db


def make_search_post(
    blog_index,
    *,
    slug,
    title,
    excerpt="Unrelated excerpt",
    body_text="Unrelated body",
    tags=(),
    live=True,
):
    post = BlogPostPage(
        title=title,
        slug=slug,
        excerpt=excerpt,
        body=[("rich_text", f"<p>{body_text}</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    post.tags.add(*tags)
    if live:
        post.save_revision().publish()
    return BlogPostPage.objects.get(pk=post.pk)


def result_slugs(response):
    return [result["slug"] for result in response.data["results"]]


def test_search_backend_and_explicit_field_boosts(settings):
    assert settings.WAGTAILSEARCH_BACKENDS == {
        "default": {
            "BACKEND": "wagtail.search.backends.database",
            "SEARCH_CONFIG": "simple",
        }
    }

    fields = BlogPostPage.get_search_fields()
    searchable = {
        field.field_name: field.boost
        for field in fields
        if isinstance(field, index.SearchField) and not isinstance(field, index.AutocompleteField)
    }
    assert searchable["title"] == SEARCH_BOOST_TITLE == 10
    assert searchable["excerpt"] == SEARCH_BOOST_EXCERPT == 7
    assert searchable["body"] == SEARCH_BOOST_BODY == 4
    assert searchable["searchable_tag_names"] == SEARCH_BOOST_TAGS == 2
    assert any(
        isinstance(field, index.RelatedFields) and field.field_name == "tags" for field in fields
    )


def test_streamfield_search_content_is_textual_and_excludes_service_values(blog_post):
    blog_post.body = [
        ("rich_text", "<p>Visible <strong>rich text</strong></p>"),
        ("heading", {"level": "h3", "text": "Visible heading"}),
        (
            "checklist",
            [
                {"text": "Visible task", "checked": True},
                {"text": "Pending task", "checked": False},
            ],
        ),
        ("code_block", {"language": "python", "code": "print('visible code')"}),
        (
            "link",
            {
                "text": "Visible link label",
                "internal_page": None,
                "external_url": "https://internal-value.example/private",
            },
        ),
    ]

    content = blog_post.body.stream_block.get_searchable_content(blog_post.body)
    combined = "\n".join(content)

    assert "Visible rich text" in combined
    assert "Visible heading" in combined
    assert "Visible task" in combined
    assert "Pending task" in combined
    assert "visible code" in combined
    assert "Visible link label" in combined
    assert "<strong>" not in combined
    assert "h3" not in combined
    assert "python" not in combined
    assert "True" not in combined
    assert "internal-value.example" not in combined


def test_searches_title_excerpt_body_and_related_tags(blog_index):
    posts = {
        "title": make_search_post(
            blog_index,
            slug="title-match",
            title="Needle title",
        ),
        "excerpt": make_search_post(
            blog_index,
            slug="excerpt-match",
            title="Excerpt source",
            excerpt="Needle excerpt",
        ),
        "body": make_search_post(
            blog_index,
            slug="body-match",
            title="Body source",
            body_text="Needle body",
        ),
        "tag": make_search_post(
            blog_index,
            slug="tag-match",
            title="Tag source",
            tags=("Needle",),
        ),
    }

    response = APIClient().get(reverse("blog_api:post-list"), {"q": "needle"})

    assert response.status_code == 200
    assert set(result_slugs(response)) == {post.slug for post in posts.values()}


def test_search_supports_russian_english_and_mixed_unicode(blog_index):
    russian = make_search_post(
        blog_index,
        slug="русский-поиск",
        title="Архитектура Django",
        excerpt="Смешанный Unicode résumé",
        body_text="Полнотекстовый поиск",
        tags=("Питон",),
    )

    client = APIClient()
    for query in ("архитектура", "Django", "поиск", "Питон", "Архитектура Django", "résumé"):
        response = client.get(reverse("blog_api:post-list"), {"q": query})
        assert response.status_code == 200
        assert result_slugs(response) == [russian.slug], query


def test_query_and_exact_tag_filter_combine_without_duplicates(blog_index):
    matching = make_search_post(
        blog_index,
        slug="matching",
        title="Django search",
        tags=("Python", "Web"),
    )
    make_search_post(
        blog_index,
        slug="wrong-tag",
        title="Django elsewhere",
        tags=("Rust",),
    )
    make_search_post(
        blog_index,
        slug="wrong-query",
        title="Unrelated",
        tags=("Python",),
    )

    response = APIClient().get(
        reverse("blog_api:post-list"),
        {"q": "django", "tag": "python"},
    )

    assert response.status_code == 200
    assert result_slugs(response) == [matching.slug]
    assert response.data["count"] == 1
    assert APIClient().get(reverse("blog_api:post-list"), {"tag": "Python"}).data["count"] == 0


def test_search_and_tag_counts_share_live_only_visibility(blog_index):
    now = timezone.now()
    live = make_search_post(
        blog_index,
        slug="live",
        title="Visible needle",
        tags=("Shared", "Live only"),
    )
    draft = make_search_post(
        blog_index,
        slug="draft",
        title="Hidden needle",
        tags=("Shared",),
        live=False,
    )
    unpublished = make_search_post(
        blog_index,
        slug="unpublished",
        title="Hidden needle",
        tags=("Shared",),
    )
    unpublished.unpublish()
    future = make_search_post(
        blog_index,
        slug="future",
        title="Hidden needle",
        tags=("Shared",),
    )
    BlogPostPage.objects.filter(pk=future.pk).update(go_live_at=now + timedelta(hours=1))
    expired = make_search_post(
        blog_index,
        slug="expired",
        title="Hidden needle",
        tags=("Shared",),
    )
    BlogPostPage.objects.filter(pk=expired.pk).update(expire_at=now - timedelta(seconds=1))
    restricted = make_search_post(
        blog_index,
        slug="restricted",
        title="Hidden needle",
        tags=("Shared",),
    )
    PageViewRestriction.objects.create(
        page=restricted,
        restriction_type=PageViewRestriction.PASSWORD,
        password="not-a-runtime-secret",
    )

    search = APIClient().get(reverse("blog_api:post-list"), {"q": "needle"})
    tags = APIClient().get(reverse("blog_api:tag-list"))

    assert result_slugs(search) == [live.slug]
    assert tags.status_code == 200
    assert tags.data == {
        "results": [
            {"name": "Live only", "slug": "live-only", "count": 1},
            {"name": "Shared", "slug": "shared", "count": 1},
        ]
    }
    assert draft.slug not in result_slugs(search)


def test_tag_endpoint_has_constant_query_count_and_no_duplicate_counts(blog_index):
    make_search_post(
        blog_index,
        slug="first",
        title="First",
        tags=("Django", "Python"),
    )
    make_search_post(
        blog_index,
        slug="second",
        title="Second",
        tags=("Django",),
    )

    with CaptureQueriesContext(connection) as queries:
        response = APIClient().get(reverse("blog_api:tag-list"))

    assert response.status_code == 200
    # Wagtail's canonical .public() policy resolves restricted paths once,
    # followed by one aggregate tag query; the count is constant in post count.
    assert len(queries) == 2
    assert response.data == {
        "results": [
            {"name": "Django", "slug": "django", "count": 2},
            {"name": "Python", "slug": "python", "count": 1},
        ]
    }

    for number in range(8):
        make_search_post(
            blog_index,
            slug=f"more-{number}",
            title=f"More {number}",
            tags=("Django",),
        )
    with CaptureQueriesContext(connection) as more_queries:
        more_response = APIClient().get(reverse("blog_api:tag-list"))

    assert more_response.status_code == 200
    assert len(more_queries) == len(queries)
    assert more_response.data["results"][0]["count"] == 10


def test_search_list_query_count_is_constant_in_result_count(blog_index):
    make_search_post(
        blog_index,
        slug="bounded-0",
        title="Bounded search 0",
        tags=("Django",),
    )
    with CaptureQueriesContext(connection) as one_post_queries:
        one_post_response = APIClient().get(
            reverse("blog_api:post-list"),
            {"q": "bounded", "page_size": 50},
        )

    for number in range(1, 10):
        make_search_post(
            blog_index,
            slug=f"bounded-{number}",
            title=f"Bounded search {number}",
            tags=("Django",),
        )
    with CaptureQueriesContext(connection) as ten_post_queries:
        ten_post_response = APIClient().get(
            reverse("blog_api:post-list"),
            {"q": "bounded", "page_size": 50},
        )

    assert one_post_response.data["count"] == 1
    assert ten_post_response.data["count"] == 10
    assert len(ten_post_queries) == len(one_post_queries)


def test_republication_refreshes_changed_tag_search_document(blog_index):
    post = make_search_post(
        blog_index,
        slug="retagged",
        title="Tag refresh",
        tags=("Before",),
    )
    assert result_slugs(APIClient().get(reverse("blog_api:post-list"), {"q": "before"})) == [
        post.slug
    ]

    post.tags.set(["После"])
    post.save_revision().publish()

    old = APIClient().get(reverse("blog_api:post-list"), {"q": "before"})
    new = APIClient().get(reverse("blog_api:post-list"), {"q": "После"})
    assert result_slugs(old) == []
    assert result_slugs(new) == [post.slug]


def test_pagination_links_remain_relative_and_preserve_filters(blog_index):
    for number in range(5):
        make_search_post(
            blog_index,
            slug=f"match-{number}",
            title=f"Общий Django {number}",
            tags=("Питон",),
        )

    client = APIClient()
    first = client.get(
        reverse("blog_api:post-list"),
        {"q": "Общий Django", "tag": "питон", "page_size": 2},
    )
    second = client.get(
        reverse("blog_api:post-list"),
        {"q": "Общий Django", "tag": "питон", "page_size": 2, "page": 2},
    )

    assert first.status_code == second.status_code == 200
    assert first.data["count"] == 5
    assert first.data["next"].startswith("/api/v1/posts/?")
    assert "http://" not in first.data["next"]
    first_query = parse_qs(urlsplit(first.data["next"]).query)
    previous_query = parse_qs(urlsplit(second.data["previous"]).query)
    assert first_query == {
        "q": ["Общий Django"],
        "tag": ["питон"],
        "page_size": ["2"],
        "page": ["2"],
    }
    assert previous_query == {
        "q": ["Общий Django"],
        "tag": ["питон"],
        "page_size": ["2"],
    }


@pytest.mark.parametrize("parameter", ["q", "tag", "page", "page_size"])
def test_repeated_supported_parameters_are_rejected(parameter):
    response = APIClient().get(f"{reverse('blog_api:post-list')}?{parameter}=one&{parameter}=two")

    assert response.status_code == 400
    assert response.data[parameter] == ["This parameter may be provided only once."]


@pytest.mark.parametrize(
    ("query_string", "field"),
    [
        (f"q={'x' * (MAX_QUERY_CODE_POINTS + 1)}", "q"),
        ("q=valid%00hidden", "q"),
        ("q=valid%0Ahidden", "q"),
        ("tag=not%20a%20slug", "tag"),
        ("tag=parent%2Fchild", "tag"),
        ("page=0", "page"),
        ("page_size=invalid", "page_size"),
    ],
)
def test_invalid_query_shapes_return_sanitized_400(query_string, field):
    response = APIClient().get(f"{reverse('blog_api:post-list')}?{query_string}")

    assert response.status_code == 400
    assert set(response.data) == {field}
    assert "parent/child" not in response.content.decode()
    assert "valid\\u0000hidden" not in response.content.decode()


def test_empty_query_is_absent_and_unknown_unicode_tag_is_empty(blog_index):
    post = make_search_post(
        blog_index,
        slug="ordinary",
        title="Ordinary feed",
        tags=("Known",),
    )

    empty_query = APIClient().get(reverse("blog_api:post-list"), {"q": " \u00a0 "})
    unknown_tag = APIClient().get(
        reverse("blog_api:post-list"),
        {"tag": "неизвестный-тег"},
    )

    assert result_slugs(empty_query) == [post.slug]
    assert unknown_tag.status_code == 200
    assert unknown_tag.data["count"] == 0
    assert unknown_tag.data["results"] == []


@pytest.mark.postgresql
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="PostgreSQL ranking assertion",
)
def test_postgresql_ranking_respects_weights_and_pk_tie_break(blog_index):
    title = make_search_post(
        blog_index,
        slug="title-rank",
        title="Rankneedle",
    )
    excerpt = make_search_post(
        blog_index,
        slug="excerpt-rank",
        title="Excerpt",
        excerpt="Rankneedle",
    )
    body = make_search_post(
        blog_index,
        slug="body-rank",
        title="Body",
        body_text="Rankneedle",
    )
    tag = make_search_post(
        blog_index,
        slug="tag-rank",
        title="Tag",
        tags=("Rankneedle",),
    )
    tied_lower_pk = make_search_post(
        blog_index,
        slug="tie-lower",
        title="Rankneedle",
    )

    response = APIClient().get(reverse("blog_api:post-list"), {"q": "rankneedle"})

    assert response.status_code == 200
    slugs = result_slugs(response)
    assert slugs.index(tied_lower_pk.slug) < slugs.index(title.slug)
    assert slugs.index(title.slug) < slugs.index(excerpt.slug)
    assert slugs.index(excerpt.slug) < slugs.index(body.slug)
    assert slugs.index(body.slug) < slugs.index(tag.slug)


@pytest.mark.postgresql
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="PostgreSQL display-date ordering assertion",
)
def test_postgresql_feed_uses_coalesce_display_date_and_deterministic_pk_ties(
    blog_index,
):
    display_date = timezone.now() - timedelta(days=30)
    lower_pk = make_search_post(
        blog_index,
        slug="display-tie-lower",
        title="Display tie lower",
    )
    higher_pk = make_search_post(
        blog_index,
        slug="display-tie-higher",
        title="Display tie higher",
    )
    BlogPostPage.objects.filter(pk__in=(lower_pk.pk, higher_pk.pk)).update(
        original_published_at=display_date
    )

    queryset = public_blog_posts()
    response = APIClient().get(reverse("blog_api:post-list"))
    plan = queryset.explain()

    assert "COALESCE" in str(queryset.query).upper()
    assert "SORT KEY" in plan.upper()
    assert "COALESCE" in plan.upper()
    assert result_slugs(response)[:2] == [higher_pk.slug, lower_pk.slug]
