import pytest
from django.core.exceptions import ValidationError
from wagtail.models import Page

from apps.blog.blocks import RICH_TEXT_FEATURES, BlogBodyBlock

pytestmark = pytest.mark.django_db


def all_block_values(wagtail_image):
    root = Page.get_first_root_node()
    image_value = {
        "image": wagtail_image.pk,
        "decorative": False,
        "alt_text": "A descriptive alt",
    }
    return [
        {"type": "rich_text", "value": "<p><strong>Rich text</strong></p>"},
        {"type": "heading", "value": {"level": "h2", "text": "Section"}},
        {"type": "image", "value": image_value},
        {"type": "gallery", "value": [image_value, image_value]},
        {
            "type": "quote",
            "value": {"text": "A useful quotation.", "attribution": "Author"},
        },
        {"type": "bulleted_list", "value": ["First", "Second"]},
        {"type": "numbered_list", "value": ["First", "Second"]},
        {
            "type": "checklist",
            "value": [
                {"text": "Done", "checked": True},
                {"text": "Pending", "checked": False},
            ],
        },
        {"type": "inline_code", "value": "print(value)"},
        {
            "type": "code_block",
            "value": {"language": "python", "code": "print('hello')"},
        },
        {
            "type": "table",
            "value": {
                "data": [["Name", "Value"], ["answer", "42"]],
                "table_header_choice": "row",
                "first_row_is_table_header": True,
                "first_col_is_header": False,
            },
        },
        {"type": "horizontal_divider", "value": None},
        {
            "type": "link",
            "value": {
                "text": "Internal link",
                "internal_page": root.pk,
                "external_url": "",
            },
        },
    ]


def test_block_library_has_stable_first_version_types():
    body_block = BlogBodyBlock()

    assert list(body_block.child_blocks) == [
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
    assert "embed" not in body_block.child_blocks
    assert all(
        block.__class__.__name__ != "RawHTMLBlock" for block in body_block.child_blocks.values()
    )


def test_block_chooser_has_descriptions_and_editorial_groups():
    body_block = BlogBodyBlock()
    grouped = {
        group: [block.name for block in child_blocks]
        for group, child_blocks in body_block.grouped_child_blocks()
    }

    assert grouped == {
        "Text": ["rich_text", "heading", "quote"],
        "Media": ["image", "gallery"],
        "Lists": ["bulleted_list", "numbered_list", "checklist"],
        "Code / Data": ["inline_code", "code_block", "table"],
        "Structure": ["horizontal_divider", "link"],
    }
    assert all(block.meta.description for block in body_block.child_blocks.values())
    assert grouped["Text"][:2] == ["rich_text", "heading"]
    assert grouped["Media"][0] == "image"
    assert grouped["Text"][2] == "quote"


def test_all_streamfield_blocks_convert_and_validate(wagtail_image):
    body_block = BlogBodyBlock()
    value = body_block.to_python(all_block_values(wagtail_image))

    cleaned_value = body_block.clean(value)

    assert [block.block_type for block in cleaned_value] == list(body_block.child_blocks)
    assert cleaned_value[9].value["language"] == "python"


def test_rich_text_features_are_explicit_and_exclude_headings():
    rich_text_block = BlogBodyBlock().child_blocks["rich_text"]

    assert rich_text_block.features == RICH_TEXT_FEATURES
    assert not {"h1", "h2", "h3", "h4", "image", "embed"} & set(rich_text_block.features)


def test_heading_rejects_h1():
    heading_block = BlogBodyBlock().child_blocks["heading"]

    with pytest.raises(ValidationError):
        heading_block.clean(heading_block.to_python({"level": "h1", "text": "Invalid"}))


def test_image_requires_alt_text_or_decorative_flag(wagtail_image):
    image_block = BlogBodyBlock().child_blocks["image"]
    missing_alt = image_block.to_python(
        {"image": wagtail_image.pk, "decorative": False, "alt_text": ""}
    )

    with pytest.raises(ValidationError):
        image_block.clean(missing_alt)

    decorative = image_block.to_python(
        {"image": wagtail_image.pk, "decorative": True, "alt_text": ""}
    )
    assert image_block.clean(decorative).decorative is True


def test_gallery_requires_at_least_two_images(wagtail_image):
    gallery_block = BlogBodyBlock().child_blocks["gallery"]
    one_image = gallery_block.to_python(
        [
            {
                "image": wagtail_image.pk,
                "decorative": False,
                "alt_text": "Only image",
            }
        ]
    )

    with pytest.raises(ValidationError):
        gallery_block.clean(one_image)


def test_code_language_is_normalized_and_validated():
    language_block = BlogBodyBlock().child_blocks["code_block"].child_blocks["language"]

    assert language_block.clean("  PyThOn  ") == "python"
    assert language_block.get_prep_value("  PyThOn  ") == "python"
    with pytest.raises(ValidationError):
        language_block.clean("python script")


@pytest.mark.parametrize(
    "value",
    [
        {"text": "Missing", "internal_page": None, "external_url": ""},
        {
            "text": "Conflicting",
            "internal_page": "root",
            "external_url": "https://example.com",
        },
    ],
)
def test_link_requires_exactly_one_destination(value):
    link_block = BlogBodyBlock().child_blocks["link"]
    if value["internal_page"] == "root":
        value["internal_page"] = Page.get_first_root_node().pk

    with pytest.raises(ValidationError):
        link_block.clean(link_block.to_python(value))


def test_link_rejects_non_http_external_url():
    link_block = BlogBodyBlock().child_blocks["link"]
    value = link_block.to_python(
        {"text": "FTP", "internal_page": None, "external_url": "ftp://example.com/file"}
    )

    with pytest.raises(ValidationError):
        link_block.clean(value)
