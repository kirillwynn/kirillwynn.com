import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from wagtail import blocks
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.images.blocks import ImageBlock

RICH_TEXT_FEATURES = ["bold", "italic", "link"]
LANGUAGE_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_+#.-]{0,31}$")


class LanguageIdentifierBlock(blocks.CharBlock):
    """A storage-safe, frontend-agnostic syntax language identifier."""

    def __init__(self, **kwargs):
        validators = list(kwargs.pop("validators", ()))
        validators.append(
            RegexValidator(
                LANGUAGE_IDENTIFIER_PATTERN,
                "Use a lowercase language identifier such as python, js, or c++.",
            )
        )
        super().__init__(max_length=32, validators=validators, **kwargs)

    def clean(self, value):
        normalized_value = value.strip().lower() if isinstance(value, str) else value
        return super().clean(normalized_value)

    def get_prep_value(self, value):
        return value.strip().lower() if isinstance(value, str) else value


class HeadingBlock(blocks.StructBlock):
    level = blocks.ChoiceBlock(
        choices=[
            ("h2", "Heading 2"),
            ("h3", "Heading 3"),
            ("h4", "Heading 4"),
        ],
        default="h2",
    )
    text = blocks.CharBlock(max_length=200)

    class Meta:
        icon = "title"
        label = "Heading"


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(rows=3, max_length=2_000)
    attribution = blocks.CharBlock(required=False, max_length=200)

    class Meta:
        icon = "openquote"
        label = "Quote"


class ChecklistItemBlock(blocks.StructBlock):
    text = blocks.CharBlock(max_length=500)
    checked = blocks.BooleanBlock(required=False, default=False)

    class Meta:
        label = "Checklist item"


class CodeBlock(blocks.StructBlock):
    language = LanguageIdentifierBlock(
        help_text="Lowercase language identifier used by a future syntax highlighter."
    )
    code = blocks.TextBlock(rows=12)

    class Meta:
        icon = "code"
        label = "Code block"


class LinkBlock(blocks.StructBlock):
    text = blocks.CharBlock(max_length=200)
    internal_page = blocks.PageChooserBlock(required=False)
    external_url = blocks.URLBlock(
        required=False,
        max_length=2_048,
        validators=[URLValidator(schemes=["http", "https"])],
    )

    def clean(self, value):
        cleaned_value = super().clean(value)
        has_internal_page = bool(cleaned_value.get("internal_page"))
        has_external_url = bool(cleaned_value.get("external_url"))

        if has_internal_page == has_external_url:
            message = "Choose exactly one destination: an internal page or an external URL."
            raise blocks.StructBlockValidationError(
                block_errors={
                    "internal_page": ValidationError(message),
                    "external_url": ValidationError(message),
                }
            )

        return cleaned_value

    class Meta:
        icon = "link"
        label = "Link"


class BlogBodyBlock(blocks.StreamBlock):
    rich_text = blocks.RichTextBlock(features=RICH_TEXT_FEATURES)
    heading = HeadingBlock()
    image = ImageBlock()
    gallery = blocks.ListBlock(ImageBlock(), min_num=2, max_num=12)
    quote = QuoteBlock()
    bulleted_list = blocks.ListBlock(
        blocks.CharBlock(max_length=500),
        min_num=1,
        label="Bulleted list",
    )
    numbered_list = blocks.ListBlock(
        blocks.CharBlock(max_length=500),
        min_num=1,
        label="Numbered list",
    )
    checklist = blocks.ListBlock(ChecklistItemBlock(), min_num=1)
    inline_code = blocks.CharBlock(max_length=500, icon="code")
    code_block = CodeBlock()
    table = TableBlock(
        table_options={
            "minSpareRows": 0,
            "startRows": 3,
            "startCols": 3,
        }
    )
    horizontal_divider = blocks.StaticBlock(
        admin_text="A horizontal divider.",
        icon="horizontalrule",
    )
    link = LinkBlock()

    class Meta:
        label = "Post body"
        min_num = 1
