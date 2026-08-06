import copy
import json
import uuid
from datetime import UTC, datetime

import pytest
from django.urls import reverse
from wagtail.admin.rich_text import get_rich_text_editor_widget
from wagtail.models import Page, Revision

from apps.blog.blocks import RICH_TEXT_FEATURES, BlogBodyBlock
from apps.blog.models import BlogPostPage
from apps.blog.widgets import AccessibleDraftailRichTextArea
from apps.subscriptions.models import EmailDelivery, EmailOutbox

pytestmark = pytest.mark.django_db


def all_block_values(image_id, internal_page_id):
    image = {
        "image": image_id,
        "decorative": False,
        "alt_text": "Stage 19B round-trip image",
    }
    return [
        {
            "type": "rich_text",
            "value": (
                "<p><strong>Bold</strong> and <em>italic</em> with "
                '<a href="https://example.com/reference?q=1&amp;x=2">an external link</a> '
                f'and <a linktype="page" id="{internal_page_id}">an internal link</a>.</p>'
            ),
        },
        {"type": "heading", "value": {"level": "h2", "text": "Long-form heading"}},
        {"type": "image", "value": image},
        {"type": "gallery", "value": [image, image]},
        {
            "type": "quote",
            "value": {"text": "A calm editing surface.", "attribution": "Stage 19B"},
        },
        {"type": "bulleted_list", "value": ["First bullet", "Second bullet"]},
        {"type": "numbered_list", "value": ["First step", "Second step"]},
        {
            "type": "checklist",
            "value": [
                {"text": "Draft", "checked": True},
                {"text": "Review", "checked": False},
            ],
        },
        {"type": "inline_code", "value": "python manage.py check"},
        {
            "type": "code_block",
            "value": {"language": "python", "code": "print('stage 19b')"},
        },
        {
            "type": "table",
            "value": {
                "data": [["Contract", "Result"], ["Storage", "Preserved"]],
                "table_header_choice": "row",
                "first_row_is_table_header": True,
                "first_col_is_header": False,
            },
        },
        {"type": "horizontal_divider", "value": None},
        {
            "type": "link",
            "value": {
                "text": "Internal destination",
                "internal_page": internal_page_id,
                "external_url": "",
            },
        },
    ]


def canonical_stream_json(value):
    return json.dumps(list(value), ensure_ascii=False, separators=(",", ":"))


def edited_block_value(block_type, image_id):
    image = {
        "image": image_id,
        "decorative": False,
        "alt_text": "Edited Stage 19B image",
    }
    return {
        "rich_text": '<p>Edited <b>rich text</b> with <a href="https://example.org/">a link</a>.</p>',
        "heading": {"level": "h3", "text": "Edited heading"},
        "image": image,
        "gallery": [image, {**image, "alt_text": "Second edited image"}],
        "quote": {"text": "Edited quotation.", "attribution": "Editor"},
        "bulleted_list": ["Edited bullet", "Another bullet"],
        "numbered_list": ["Edited step", "Another step"],
        "checklist": [
            {"text": "Edited task", "checked": False},
            {"text": "Completed task", "checked": True},
        ],
        "inline_code": "python manage.py test",
        "code_block": {"language": "js", "code": "console.log('edited')"},
        "table": {
            "data": [["Contract", "Result"], ["Editing", "Preserved"]],
            "table_header_choice": "row",
            "first_row_is_table_header": True,
            "first_col_is_header": False,
        },
        "horizontal_divider": None,
        "link": {
            "text": "External destination",
            "internal_page": None,
            "external_url": "https://example.org/reference",
        },
    }[block_type]


EDITED_BLOCK_MARKERS = {
    "rich_text": "Edited",
    "heading": "Edited heading",
    "image": "Edited Stage 19B image",
    "gallery": "Second edited image",
    "quote": "Edited quotation",
    "bulleted_list": "Edited bullet",
    "numbered_list": "Edited step",
    "checklist": "Edited task",
    "inline_code": "manage.py test",
    "code_block": "console.log('edited')",
    "table": "Editing",
    "link": "External destination",
}


def test_draftail_widget_no_change_round_trip_preserves_supported_database_html(blog_index):
    widget = get_rich_text_editor_widget("default", features=RICH_TEXT_FEATURES)
    assert isinstance(widget, AccessibleDraftailRichTextArea)
    assert widget.options["ariaLabel"] == "Rich text editor"
    imported_html = (
        "<p><strong>Bold</strong> and <em>italic</em> with "
        '<a href="https://example.com/reference?q=1&amp;x=2">external</a> and '
        f'<a linktype="page" id="{blog_index.pk}">internal</a>.</p>'
    )
    imported_content_state = widget.format_value(imported_html)
    database_html = widget.value_from_datadict(
        {"body": imported_content_state},
        {},
        "body",
    )

    content_state = widget.format_value(database_html)
    round_tripped = widget.value_from_datadict(
        {"body": content_state},
        {},
        "body",
    )

    assert round_tripped == database_html
    assert '<a href="https://example.com/reference?q=1&amp;x=2">external</a>' in round_tripped
    assert f'<a id="{blog_index.pk}" linktype="page">internal</a>' not in round_tripped
    assert f'<a linktype="page" id="{blog_index.pk}">internal</a>' in round_tripped
    assert "<b>Bold</b>" in round_tripped
    assert "<i>italic</i>" in round_tripped


def test_draftail_converter_rejects_unsafe_database_markup():
    widget = get_rich_text_editor_widget("default", features=RICH_TEXT_FEATURES)
    unsafe_html = (
        '<p>Safe <script>alert(1)</script><img src="x" onerror="alert(2)" /> '
        '<a href="javascript:alert(3)" onclick="alert(4)">link</a></p>'
    )

    content_state = widget.format_value(unsafe_html)
    cleaned = widget.value_from_datadict({"body": content_state}, {}, "body")

    assert "Safe" in cleaned
    assert "script" not in cleaned.lower()
    assert "onerror" not in cleaned.lower()
    assert "onclick" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()


def test_all_thirteen_blocks_survive_revision_preview_publish_and_structural_edits(
    blog_post,
    wagtail_image,
):
    body_block = BlogBodyBlock()
    imported_body = body_block.to_python(
        all_block_values(wagtail_image.pk, Page.get_first_root_node().pk),
    )
    blog_post.body = body_block.to_python(body_block.get_prep_value(imported_body))
    blog_post.notify_subscribers_on_first_publication = False
    blog_post.original_published_at = datetime(2020, 4, 3, 12, tzinfo=UTC)
    blog_post.save()
    bootstrap_revision = blog_post.save_revision()
    blog_post.body = body_block.to_python(bootstrap_revision.content["body"])
    blog_post.save(update_fields=("body",))

    persisted_before = BlogPostPage.objects.get(pk=blog_post.pk).body.raw_data
    original_json = canonical_stream_json(persisted_before)
    original_ids = [item["id"] for item in persisted_before]
    original_types = [item["type"] for item in persisted_before]

    unchanged_revision = blog_post.save_revision()
    reopened = unchanged_revision.as_object()

    assert canonical_stream_json(reopened.body.raw_data) == original_json
    assert [item["id"] for item in reopened.body.raw_data] == original_ids
    assert [item["type"] for item in reopened.body.raw_data] == original_types
    assert original_types == list(body_block.child_blocks)

    edited = copy.deepcopy(reopened.body.raw_data)
    edited[1]["value"]["text"] = "Edited long-form heading"
    duplicate = copy.deepcopy(edited[0])
    duplicate["id"] = str(uuid.uuid4())
    reordered = [edited[-1], duplicate, *edited[:-1]]
    deleted_quote = [item for item in reordered if item["type"] != "quote"]
    reopened.body = body_block.to_python(deleted_quote)

    edited_revision = reopened.save_revision()
    edited_draft = edited_revision.as_object()
    edited_types = [item["type"] for item in edited_draft.body.raw_data]

    assert edited_types[:3] == ["link", "rich_text", "rich_text"]
    assert "quote" not in edited_types
    assert len(edited_draft.body.raw_data) == 13
    assert edited_draft.body.raw_data[1]["id"] == duplicate["id"]
    assert edited_draft.body.raw_data[2]["id"] == original_ids[0]

    preview = edited_draft.make_preview_request(preview_mode="backend")
    assert preview.status_code == 200
    assert "Edited long-form heading" in preview.rendered_content
    assert "stage 19b" in preview.rendered_content
    assert "Internal destination" in preview.rendered_content

    edited_revision.publish()
    published = BlogPostPage.objects.get(pk=blog_post.pk)
    assert published.live is True
    assert canonical_stream_json(published.body.raw_data) == canonical_stream_json(
        edited_draft.body.raw_data
    )
    assert Revision.page_revisions.filter(object_id=blog_post.pk).count() == 3
    assert not EmailOutbox.objects.exists()
    assert not EmailDelivery.objects.exists()


@pytest.mark.parametrize("block_type", list(BlogBodyBlock().child_blocks))
def test_each_block_survives_add_edit_reorder_duplicate_delete_reopen_preview_and_publish(
    block_type,
    blog_post,
    wagtail_image,
):
    body_block = BlogBodyBlock()
    blog_post.notify_subscribers_on_first_publication = False
    blog_post.body = body_block.clean(
        body_block.to_python(all_block_values(wagtail_image.pk, Page.get_first_root_node().pk))
    )
    blog_post.save()
    initial_revision = blog_post.save_revision()
    draft = initial_revision.as_object()
    initial_raw = copy.deepcopy(draft.body.raw_data)
    target_index = [item["type"] for item in initial_raw].index(block_type)
    original_id = initial_raw[target_index]["id"]

    changed_value = edited_block_value(block_type, wagtail_image.pk)
    initial_raw[target_index]["value"] = changed_value
    duplicate = copy.deepcopy(initial_raw[target_index])
    duplicate["id"] = str(uuid.uuid4())
    structurally_edited = [
        duplicate,
        *(item for item in initial_raw if item["id"] != original_id),
    ]

    draft.body = body_block.clean(body_block.to_python(structurally_edited))
    edited_revision = draft.save_revision()
    reopened = edited_revision.as_object()
    reopened_raw = reopened.body.raw_data

    assert len(reopened_raw) == 13
    assert reopened_raw[0]["type"] == block_type
    assert reopened_raw[0]["id"] == duplicate["id"]
    if block_type == "horizontal_divider":
        assert reopened_raw[0]["value"] is None
    else:
        assert EDITED_BLOCK_MARKERS[block_type] in json.dumps(
            reopened_raw[0]["value"],
            ensure_ascii=False,
        )
    assert original_id not in {item["id"] for item in reopened_raw}

    preview = reopened.make_preview_request(preview_mode="backend")
    assert preview.status_code == 200
    assert preview.rendered_content

    edited_revision.publish()
    published = BlogPostPage.objects.get(pk=blog_post.pk)
    assert published.live is True
    assert canonical_stream_json(published.body.raw_data) == canonical_stream_json(reopened_raw)
    assert not EmailOutbox.objects.exists()
    assert not EmailDelivery.objects.exists()


def test_stage19b_editor_assets_are_scoped_away_from_django_admin_and_other_pages(
    client,
    blog_index,
    blog_post,
):
    user_model = blog_post.owner.__class__
    superuser = user_model.objects.create_superuser(
        username="stage19b-scope-owner",
        email="stage19b-scope@example.com",
        password="safe-test-password",
    )
    client.force_login(superuser)

    post_editor = client.get(
        reverse("wagtailadmin_pages:edit", args=(blog_post.pk,)),
    )
    index_editor = client.get(
        reverse("wagtailadmin_pages:edit", args=(blog_index.pk,)),
    )
    django_admin = client.get(reverse("admin:index"))

    assert post_editor.status_code == 200
    assert b'data-editorial-surface="writing"' in post_editor.content
    assert b"blog/css/editorial-admin.css" in post_editor.content
    assert b"blog/js/editorial-admin.js" in post_editor.content
    assert index_editor.status_code == 200
    assert b'data-editorial-surface="writing"' not in index_editor.content
    assert django_admin.status_code == 200
    assert b"blog/css/editorial-admin.css" not in django_admin.content
    assert b"blog/js/editorial-admin.js" not in django_admin.content
    assert b'data-editorial-surface="writing"' not in django_admin.content
