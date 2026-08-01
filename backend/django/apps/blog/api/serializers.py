from datetime import UTC
from urllib.parse import urlparse

from django.conf import settings
from django.utils.encoding import iri_to_uri
from rest_framework import serializers
from wagtail.images import get_image_model
from wagtail.rich_text import expand_db_html

from apps.blog.services.content_routes import frontend_page_path
from apps.users.services import is_site_author, public_display_name

API_VERSION = "1.0"
IMAGE_RENDITION_SPECS = {
    "480w": "width-480",
    "960w": "width-960",
    "1440w": "width-1440",
}


def _timestamp(value):
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _absolute_url(url):
    if not url:
        return None
    if urlparse(url).scheme in {"http", "https"}:
        return url
    path = url if url.startswith("/") else f"/{url}"
    return f"{settings.PUBLIC_SITE_URL}{iri_to_uri(path)}"


def _image_context(image):
    alt = getattr(image, "contextual_alt_text", None)
    decorative = bool(getattr(image, "decorative", False))
    if alt is None:
        alt = "" if decorative else image.title
    return alt, decorative


def serialize_image(image, *, alt=None, decorative=None):
    if image is None:
        return None

    default_alt, default_decorative = _image_context(image)
    if alt is None:
        alt = default_alt
    if decorative is None:
        decorative = default_decorative
    renditions = image.get_renditions(*IMAGE_RENDITION_SPECS.values())
    return {
        "id": image.pk,
        "title": image.title,
        "alt": alt,
        "decorative": decorative,
        "width": image.width,
        "height": image.height,
        "renditions": {
            name: {
                "url": _absolute_url(renditions[spec].url),
                "width": renditions[spec].width,
                "height": renditions[spec].height,
            }
            for name, spec in IMAGE_RENDITION_SPECS.items()
        },
    }


def _serialize_table(value):
    rows = value.get("data") or []
    row_header = bool(
        value.get("first_row_is_table_header")
        or value.get("table_header_choice") in {"row", "both"}
    )
    column_header = bool(
        value.get("first_col_is_header") or value.get("table_header_choice") in {"column", "both"}
    )
    return {
        "rows": [["" if cell is None else str(cell) for cell in row] for row in rows],
        "header": {
            "row": row_header,
            "column": column_header,
        },
    }


def serialize_body(body):
    serialized = []
    for block in body:
        block_type = block.block_type
        value = block.value

        if block_type == "rich_text":
            source = getattr(value, "source", str(value))
            serialized_value = {"html": expand_db_html(source)}
        elif block_type == "heading":
            serialized_value = {
                "level": value["level"],
                "text": value["text"],
            }
        elif block_type == "image":
            serialized_value = serialize_image(value)
        elif block_type == "gallery":
            serialized_value = {"images": [serialize_image(image) for image in value]}
        elif block_type == "quote":
            serialized_value = {
                "text": value["text"],
                "attribution": value["attribution"] or None,
            }
        elif block_type in {"bulleted_list", "numbered_list"}:
            serialized_value = {"items": [str(item) for item in value]}
        elif block_type == "checklist":
            serialized_value = {
                "items": [
                    {
                        "text": item["text"],
                        "checked": bool(item["checked"]),
                    }
                    for item in value
                ]
            }
        elif block_type == "inline_code":
            serialized_value = {"code": str(value)}
        elif block_type == "code_block":
            serialized_value = {
                "language": value["language"],
                "code": value["code"],
            }
        elif block_type == "table":
            serialized_value = _serialize_table(value)
        elif block_type == "horizontal_divider":
            serialized_value = {}
        elif block_type == "link":
            internal_page = value["internal_page"]
            if internal_page:
                serialized_value = {
                    "text": value["text"],
                    "kind": "internal",
                    "href": frontend_page_path(internal_page),
                    "target": {
                        "id": internal_page.pk,
                        "type": internal_page.specific_class._meta.label_lower,
                        "slug": internal_page.slug,
                    },
                }
            else:
                serialized_value = {
                    "text": value["text"],
                    "kind": "external",
                    "href": value["external_url"],
                    "target": None,
                }
        else:
            raise ValueError(f"Unsupported body block type: {block_type}")

        serialized.append(
            {
                "id": str(block.id),
                "type": block_type,
                "value": serialized_value,
            }
        )
    return serialized


def _tags(page):
    return [
        {"name": tag.name, "slug": tag.slug}
        for tag in sorted(page.tags.all(), key=lambda item: (item.slug, item.name))
    ]


def _fallback_body_image(page):
    for block in page.body:
        if block.block_type == "image":
            return block.value
        if block.block_type == "gallery" and block.value:
            return block.value[0]
    return None


def prepare_list_lead_images(pages):
    raw_fallbacks = {}
    body_image_ids = set()
    for page in pages:
        if page.open_graph_image_id:
            continue
        for block in page.body.raw_data:
            block_type = block.get("type")
            value = block.get("value")
            if block_type == "image" and isinstance(value, dict):
                raw_image = value
            elif block_type == "gallery" and isinstance(value, list) and value:
                raw_image = value[0]
            else:
                continue

            if isinstance(raw_image, dict) and raw_image.get("image"):
                image_id = int(raw_image["image"])
                raw_fallbacks[page.pk] = (
                    image_id,
                    raw_image.get("alt_text", ""),
                    bool(raw_image.get("decorative", False)),
                )
                body_image_ids.add(image_id)
            break

    body_images = {
        image.pk: image
        for image in get_image_model()
        .objects.filter(pk__in=body_image_ids)
        .prefetch_related("renditions")
    }
    result = {}
    for page in pages:
        if page.open_graph_image:
            result[page.pk] = (page.open_graph_image, None, None)
        elif page.pk in raw_fallbacks:
            image_id, alt, decorative = raw_fallbacks[page.pk]
            image = body_images.get(image_id)
            if image:
                result[page.pk] = (image, alt, decorative)
    return result


def _metadata(page, *, lead_image=None):
    path = f"/posts/{page.slug}"
    if lead_image is None:
        image = page.open_graph_image or _fallback_body_image(page)
        image_data = serialize_image(image)
    else:
        image, alt, decorative = lead_image
        image_data = serialize_image(
            image,
            alt=alt,
            decorative=decorative,
        )
    return {
        "api_version": API_VERSION,
        "id": page.pk,
        "slug": page.slug,
        "title": page.title,
        "excerpt": page.excerpt,
        "published_at": _timestamp(page.first_published_at),
        "updated_at": _timestamp(page.last_published_at),
        "original_published_at": _timestamp(page.original_published_at),
        "display_published_at": _timestamp(page.display_published_at),
        "author": {
            "id": page.owner.pk,
            "display_name": public_display_name(page.owner),
            "is_site_author": is_site_author(page.owner),
        },
        "tags": _tags(page),
        "canonical_path": path,
        "canonical_url": page.canonical_url or f"{settings.PUBLIC_SITE_URL}{iri_to_uri(path)}",
        "seo": {
            "title": page.seo_title or page.title,
            "description": page.search_description or page.excerpt,
        },
        "open_graph": {
            "title": page.open_graph_title or page.seo_title or page.title,
            "description": (page.open_graph_description or page.search_description or page.excerpt),
            "image": image_data,
        },
    }


class PostListSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        data = _metadata(
            instance,
            lead_image=self.context["lead_images"].get(instance.pk),
        )
        data["lead_image"] = data["open_graph"]["image"]
        return data


class PostDetailSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        data = _metadata(instance)
        data["body"] = serialize_body(instance.body)
        return data
