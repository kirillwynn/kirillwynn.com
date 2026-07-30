from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import struct
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from PIL import Image, ImageCms, ImageSequence, UnidentifiedImageError

MANIFEST_SCHEMA_VERSION = 1
ATTESTATION_SCHEMA_VERSION = 1
NORMALIZER_VERSION = "pillow-12.3-reaction-v1"
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
MAX_SOURCE_BYTES = 512 * 1024
MAX_OUTPUT_BYTES = 512 * 1024
MAX_DIMENSION = 512
MAX_FRAME_COUNT = 160
MAX_DURATION_MS = 10_000
MAX_DECODED_RGBA_BYTES = 64 * 1024 * 1024
MIN_FRAME_DELAY_MS = 20
CATALOG_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SOURCE_VERSION = re.compile(r"^source-sha256-[0-9a-f]{64}$")
CONTENT_TYPES = {
    "static": "image/webp",
    "animated": "image/gif",
    "poster": "image/webp",
}
FORBIDDEN_METADATA = {
    "comment",
    "comments",
    "exif",
    "icc_profile",
    "software",
    "xmp",
    "xml:com.adobe.xmp",
}


class CatalogPipelineError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestItem:
    catalog_id: str
    source_path: str
    source_sha256: str
    display_name: str
    accessibility_label: str
    kind: str
    ordering: int
    enabled: bool
    selectable: bool
    quick_order: int | None
    provenance_source: str
    provenance_author: str
    license: str
    rights_basis: str
    approval_status: str
    immutable_asset_version: str


@dataclass(frozen=True)
class CatalogManifest:
    path: Path
    sha256: str
    catalog_id: str
    catalog_version: str
    approval_scope: str
    quick_reactions: tuple[str, str, str]
    items: tuple[ManifestItem, ...]


@dataclass(frozen=True)
class PreparedObject:
    relative_path: str
    storage_key: str
    sha256: str
    size: int
    content_type: str
    body: bytes


class ReactionObjectStore(Protocol):
    environment: str
    prefix: str

    def put_if_absent(self, item: PreparedObject, *, catalog_id: str, version: str) -> None: ...

    def verify(self, item: PreparedObject, *, catalog_id: str, version: str) -> None: ...


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _expect_object(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogPipelineError(f"{where} must be a JSON object.")
    return value


def _expect_exact_keys(value: dict[str, Any], expected: set[str], *, where: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing:
        raise CatalogPipelineError(f"{where} is missing: {', '.join(sorted(missing))}.")
    if extra:
        raise CatalogPipelineError(f"{where} has unknown fields: {', '.join(sorted(extra))}.")


def _required_string(value: Any, *, where: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CatalogPipelineError(f"{where} must be a non-empty trimmed string.")
    if len(value) > maximum:
        raise CatalogPipelineError(f"{where} is longer than {maximum} characters.")
    return value


def _optional_string(value: Any, *, where: str, maximum: int) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise CatalogPipelineError(f"{where} must be a trimmed string.")
    if len(value) > maximum:
        raise CatalogPipelineError(f"{where} is longer than {maximum} characters.")
    return value


def _relative_source_path(value: Any, *, where: str) -> str:
    path = _required_string(value, where=where, maximum=240)
    if "\\" in path:
        raise CatalogPipelineError(f"{where} must use POSIX separators.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise CatalogPipelineError(f"{where} must be a traversal-free relative path.")
    return pure.as_posix()


def load_manifest(path: Path) -> CatalogManifest:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise CatalogPipelineError(f"Cannot read manifest: {error}.") from error
    try:
        document = _expect_object(json.loads(raw), where="manifest")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CatalogPipelineError("Manifest must be valid UTF-8 JSON.") from error
    root_keys = {
        "schema_version",
        "catalog_id",
        "catalog_version",
        "approval_scope",
        "quick_reactions",
        "items",
    }
    _expect_exact_keys(document, root_keys, where="manifest")
    if document["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise CatalogPipelineError(
            f"Unsupported manifest schema_version {document['schema_version']!r}."
        )
    catalog_id = _required_string(document["catalog_id"], where="catalog_id", maximum=80)
    if not CATALOG_ID.fullmatch(catalog_id):
        raise CatalogPipelineError("catalog_id must be a stable lowercase ASCII slug.")
    catalog_version = _required_string(
        document["catalog_version"], where="catalog_version", maximum=120
    )
    approval_scope = _required_string(
        document["approval_scope"], where="approval_scope", maximum=40
    )
    if approval_scope not in {"staging-only/unverified", "production-approved"}:
        raise CatalogPipelineError("approval_scope is not recognized.")
    raw_quick = document["quick_reactions"]
    if (
        not isinstance(raw_quick, list)
        or len(raw_quick) != 3
        or any(not isinstance(item, str) for item in raw_quick)
        or len(set(raw_quick)) != 3
    ):
        raise CatalogPipelineError("quick_reactions must contain exactly three distinct IDs.")
    raw_items = document["items"]
    if not isinstance(raw_items, list) or not raw_items:
        raise CatalogPipelineError("items must be a non-empty explicit allowlist.")

    expected_item_keys = {
        "catalog_id",
        "source_path",
        "source_sha256",
        "display_name",
        "accessibility_label",
        "kind",
        "ordering",
        "enabled",
        "selectable",
        "quick_order",
        "provenance",
        "license",
        "rights_basis",
        "approval_status",
        "immutable_asset_version",
    }
    items: list[ManifestItem] = []
    for index, raw_item in enumerate(raw_items):
        where = f"items[{index}]"
        item = _expect_object(raw_item, where=where)
        _expect_exact_keys(item, expected_item_keys, where=where)
        item_id = _required_string(item["catalog_id"], where=f"{where}.catalog_id", maximum=80)
        if not CATALOG_ID.fullmatch(item_id):
            raise CatalogPipelineError(f"{where}.catalog_id is not a stable ASCII slug.")
        source_hash = _required_string(
            item["source_sha256"], where=f"{where}.source_sha256", maximum=64
        )
        if not SHA256.fullmatch(source_hash):
            raise CatalogPipelineError(f"{where}.source_sha256 is not lowercase SHA-256.")
        kind = item["kind"]
        if kind not in {"static", "animated"}:
            raise CatalogPipelineError(f"{where}.kind must be static or animated.")
        ordering = item["ordering"]
        if not isinstance(ordering, int) or isinstance(ordering, bool) or ordering < 0:
            raise CatalogPipelineError(f"{where}.ordering must be a non-negative integer.")
        for field in ("enabled", "selectable"):
            if not isinstance(item[field], bool):
                raise CatalogPipelineError(f"{where}.{field} must be boolean.")
        quick_order = item["quick_order"]
        if quick_order is not None and (
            not isinstance(quick_order, int)
            or isinstance(quick_order, bool)
            or quick_order not in {1, 2, 3}
        ):
            raise CatalogPipelineError(f"{where}.quick_order must be 1, 2, 3, or null.")
        if item["selectable"] and not item["enabled"]:
            raise CatalogPipelineError(f"{where} cannot be selectable while disabled.")
        if quick_order is not None and (not item["enabled"] or not item["selectable"]):
            raise CatalogPipelineError(f"{where} quick reactions must be enabled/selectable.")
        provenance = _expect_object(item["provenance"], where=f"{where}.provenance")
        _expect_exact_keys(provenance, {"source", "author"}, where=f"{where}.provenance")
        source_version = _required_string(
            item["immutable_asset_version"],
            where=f"{where}.immutable_asset_version",
            maximum=78,
        )
        if (
            not SOURCE_VERSION.fullmatch(source_version)
            or source_version != f"source-sha256-{source_hash}"
        ):
            raise CatalogPipelineError(
                f"{where}.immutable_asset_version must attest its source SHA-256."
            )
        status = _required_string(
            item["approval_status"], where=f"{where}.approval_status", maximum=32
        )
        if status not in {"staging-only/unverified", "production-approved"}:
            raise CatalogPipelineError(f"{where}.approval_status is not recognized.")
        if approval_scope == "production-approved" and status != "production-approved":
            raise CatalogPipelineError(
                "A production-approved manifest cannot contain unverified items."
            )
        items.append(
            ManifestItem(
                catalog_id=item_id,
                source_path=_relative_source_path(
                    item["source_path"], where=f"{where}.source_path"
                ),
                source_sha256=source_hash,
                display_name=_required_string(
                    item["display_name"], where=f"{where}.display_name", maximum=120
                ),
                accessibility_label=_required_string(
                    item["accessibility_label"],
                    where=f"{where}.accessibility_label",
                    maximum=160,
                ),
                kind=kind,
                ordering=ordering,
                enabled=item["enabled"],
                selectable=item["selectable"],
                quick_order=quick_order,
                provenance_source=_required_string(
                    provenance["source"],
                    where=f"{where}.provenance.source",
                    maximum=500,
                ),
                provenance_author=_required_string(
                    provenance["author"],
                    where=f"{where}.provenance.author",
                    maximum=200,
                ),
                license=_required_string(item["license"], where=f"{where}.license", maximum=200),
                rights_basis=_required_string(
                    item["rights_basis"], where=f"{where}.rights_basis", maximum=500
                ),
                approval_status=status,
                immutable_asset_version=source_version,
            )
        )

    def duplicates(values: list[Any]) -> list[Any]:
        return sorted({value for value in values if values.count(value) > 1})

    for label, values in (
        ("catalog IDs", [item.catalog_id for item in items]),
        ("source paths", [item.source_path.casefold() for item in items]),
        ("ordering values", [item.ordering for item in items]),
    ):
        repeated = duplicates(values)
        if repeated:
            raise CatalogPipelineError(f"Duplicate {label}: {repeated!r}.")
    quick_by_order = {
        item.quick_order: item.catalog_id for item in items if item.quick_order is not None
    }
    if set(quick_by_order) != {1, 2, 3}:
        raise CatalogPipelineError("The allowlist must mark exactly three quick reactions.")
    quick_tuple = tuple(raw_quick)
    ordered_quick = tuple(quick_by_order[index] for index in (1, 2, 3))
    if quick_tuple != ordered_quick:
        raise CatalogPipelineError("quick_reactions must match item quick_order values.")
    if any(quick_id not in {item.catalog_id for item in items} for quick_id in quick_tuple):
        raise CatalogPipelineError("quick_reactions contains an unknown catalog ID.")
    return CatalogManifest(
        path=path,
        sha256=_sha256(raw),
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        approval_scope=approval_scope,
        quick_reactions=quick_tuple,  # type: ignore[arg-type]
        items=tuple(items),
    )


def _checked_source(root: Path, relative_path: str) -> Path:
    if root.is_symlink():
        raise CatalogPipelineError("The source root cannot be a symlink.")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        raise CatalogPipelineError(f"Cannot resolve source root: {error}.") from error
    if not resolved_root.is_dir():
        raise CatalogPipelineError("The source root must be a directory.")
    current = resolved_root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise CatalogPipelineError(f"Symlinks are forbidden: {relative_path}.")
    try:
        resolved = current.resolve(strict=True)
    except OSError as error:
        raise CatalogPipelineError(f"Missing source asset {relative_path}: {error}.") from error
    if not resolved.is_file() or resolved_root not in resolved.parents:
        raise CatalogPipelineError(f"Unsafe source asset path: {relative_path}.")
    return resolved


def _detect_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    raise CatalogPipelineError("Only byte-identified PNG, WebP, and GIF are accepted.")


def _validate_png_eof(data: bytes) -> None:
    if len(data) < 20:
        raise CatalogPipelineError("Truncated PNG.")
    offset = 8
    saw_iend = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise CatalogPipelineError("Truncated PNG chunk.")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise CatalogPipelineError("Truncated PNG chunk data.")
        chunk_type = data[offset + 4 : offset + 8]
        if saw_iend:
            raise CatalogPipelineError("PNG has trailing data after IEND.")
        offset = chunk_end
        if chunk_type == b"IEND":
            if length != 0:
                raise CatalogPipelineError("Malformed PNG IEND.")
            saw_iend = True
            if offset != len(data):
                raise CatalogPipelineError("PNG has trailing data after IEND.")
    if not saw_iend or offset != len(data):
        raise CatalogPipelineError("PNG does not end exactly at IEND.")


def _validate_webp_eof(data: bytes) -> None:
    if len(data) < 12:
        raise CatalogPipelineError("Truncated WebP.")
    declared = struct.unpack("<I", data[4:8])[0] + 8
    if declared != len(data):
        raise CatalogPipelineError("WebP RIFF length does not match exact file length.")


def _consume_gif_subblocks(data: bytes, offset: int) -> int:
    while True:
        if offset >= len(data):
            raise CatalogPipelineError("Truncated GIF sub-block.")
        length = data[offset]
        offset += 1
        if length == 0:
            return offset
        offset += length
        if offset > len(data):
            raise CatalogPipelineError("Truncated GIF sub-block data.")


def _validate_gif_eof(data: bytes) -> None:
    if len(data) < 14:
        raise CatalogPipelineError("Truncated GIF.")
    packed = data[10]
    offset = 13 + (3 * (2 ** ((packed & 0x07) + 1)) if packed & 0x80 else 0)
    if offset > len(data):
        raise CatalogPipelineError("Truncated GIF global color table.")
    saw_image = False
    while offset < len(data):
        marker = data[offset]
        offset += 1
        if marker == 0x3B:
            if offset != len(data):
                raise CatalogPipelineError("GIF has trailing data after its trailer.")
            if not saw_image:
                raise CatalogPipelineError("GIF has no image frame.")
            return
        if marker == 0x21:
            if offset >= len(data):
                raise CatalogPipelineError("Truncated GIF extension.")
            offset += 1
            offset = _consume_gif_subblocks(data, offset)
            continue
        if marker == 0x2C:
            saw_image = True
            if offset + 9 > len(data):
                raise CatalogPipelineError("Truncated GIF image descriptor.")
            packed = data[offset + 8]
            offset += 9
            if packed & 0x80:
                offset += 3 * (2 ** ((packed & 0x07) + 1))
            if offset >= len(data):
                raise CatalogPipelineError("Truncated GIF image data.")
            offset += 1
            offset = _consume_gif_subblocks(data, offset)
            continue
        raise CatalogPipelineError("Malformed GIF block marker.")
    raise CatalogPipelineError("GIF trailer is missing.")


def _validate_exact_container(data: bytes, detected_format: str) -> None:
    if detected_format == "PNG":
        _validate_png_eof(data)
    elif detected_format == "WEBP":
        _validate_webp_eof(data)
    else:
        _validate_gif_eof(data)


def _open_and_verify(data: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as verifier:
                verifier.verify()
            image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombWarning) as error:
        raise CatalogPipelineError(f"Image decoder rejected the asset: {error}.") from error
    width, height = image.size
    if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION:
        image.close()
        raise CatalogPipelineError(
            f"Image dimensions {width}x{height} exceed the {MAX_DIMENSION}px limit."
        )
    return image


def _convert_to_srgb(image: Image.Image, icc_profile: bytes | None) -> Image.Image:
    rgba = image.convert("RGBA")
    if not icc_profile:
        rgba.info.clear()
        return rgba
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        destination = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(
            rgba,
            source,
            destination,
            outputMode="RGBA",
            renderingIntent=ImageCms.Intent.PERCEPTUAL,
        )
    except (OSError, TypeError, ValueError) as error:
        rgba.close()
        raise CatalogPipelineError(f"Invalid or unsupported ICC profile: {error}.") from error
    rgba.close()
    converted.info.clear()
    return converted


def _lossless_webp(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(
        output,
        format="WEBP",
        lossless=True,
        method=6,
        exact=True,
    )
    data = output.getvalue()
    if len(data) > MAX_OUTPUT_BYTES:
        raise CatalogPipelineError(
            f"Normalized WebP is {len(data)} bytes; limit is {MAX_OUTPUT_BYTES}."
        )
    _validate_webp_eof(data)
    return data


def _metadata_is_stripped(data: bytes) -> None:
    with Image.open(io.BytesIO(data)) as image:
        present = FORBIDDEN_METADATA.intersection(str(key).lower() for key in image.info)
        if present:
            raise CatalogPipelineError(
                f"Normalized output still contains metadata: {sorted(present)!r}."
            )


def _prepared_object(
    *,
    catalog_id: str,
    version_sha256: str,
    content_sha256: str,
    filename: str,
    content_type: str,
    body: bytes,
) -> PreparedObject:
    storage_key = f"reactions/{catalog_id}/{version_sha256}/{filename}"
    return PreparedObject(
        relative_path=f"objects/{storage_key}",
        storage_key=storage_key,
        sha256=content_sha256,
        size=len(body),
        content_type=content_type,
        body=body,
    )


def _normalize_static(item: ManifestItem, source: bytes, detected_format: str) -> dict[str, Any]:
    if detected_format not in {"PNG", "WEBP"}:
        raise CatalogPipelineError(f"{item.catalog_id}: static assets must be PNG or WebP.")
    image = _open_and_verify(source)
    try:
        if getattr(image, "n_frames", 1) != 1:
            raise CatalogPipelineError(f"{item.catalog_id}: static asset has multiple frames.")
        image.load()
        rgba = _convert_to_srgb(image, image.info.get("icc_profile"))
        try:
            normalized = _lossless_webp(rgba)
        finally:
            rgba.close()
        _metadata_is_stripped(normalized)
        normalized_hash = _sha256(normalized)
        asset = _prepared_object(
            catalog_id=item.catalog_id,
            version_sha256=normalized_hash,
            content_sha256=normalized_hash,
            filename="asset.webp",
            content_type=CONTENT_TYPES["static"],
            body=normalized,
        )
        return {
            "width": image.width,
            "height": image.height,
            "frame_count": 1,
            "duration_ms": 0,
            "minimum_frame_delay_ms": 0,
            "asset": asset,
            "poster": None,
        }
    finally:
        image.close()


def _normalize_animated(item: ManifestItem, source: bytes, detected_format: str) -> dict[str, Any]:
    if detected_format != "GIF":
        raise CatalogPipelineError(f"{item.catalog_id}: animated assets must be GIF.")
    image = _open_and_verify(source)
    frames: list[Image.Image] = []
    try:
        frame_count = getattr(image, "n_frames", 1)
        if frame_count < 2 or frame_count > MAX_FRAME_COUNT:
            raise CatalogPipelineError(
                f"{item.catalog_id}: frame count {frame_count} is outside 2-{MAX_FRAME_COUNT}."
            )
        decoded_cost = image.width * image.height * 4 * frame_count
        if decoded_cost > MAX_DECODED_RGBA_BYTES:
            raise CatalogPipelineError(
                f"{item.catalog_id}: decoded RGBA cost {decoded_cost} exceeds "
                f"{MAX_DECODED_RGBA_BYTES}."
            )
        icc_profile = image.info.get("icc_profile")
        delays: list[int] = []
        for frame in ImageSequence.Iterator(image):
            frame.load()
            converted = _convert_to_srgb(frame, icc_profile)
            frames.append(converted)
            raw_delay = frame.info.get("duration", image.info.get("duration", 0))
            delay = raw_delay if isinstance(raw_delay, int) else 0
            delays.append(max(MIN_FRAME_DELAY_MS, delay))
        duration = sum(delays)
        if duration > MAX_DURATION_MS:
            raise CatalogPipelineError(
                f"{item.catalog_id}: normalized duration {duration}ms exceeds {MAX_DURATION_MS}ms."
            )
        output = io.BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=delays,
            loop=0,
            disposal=2,
            optimize=True,
        )
        animation = output.getvalue()
        if len(animation) > MAX_OUTPUT_BYTES:
            raise CatalogPipelineError(
                f"{item.catalog_id}: normalized GIF is {len(animation)} bytes; "
                f"limit is {MAX_OUTPUT_BYTES}."
            )
        _validate_gif_eof(animation)
        _metadata_is_stripped(animation)
        with Image.open(io.BytesIO(animation)) as verified:
            output_delays = []
            for frame in ImageSequence.Iterator(verified):
                frame.load()
                output_delays.append(frame.info.get("duration", 0))
            output_frame_count = verified.n_frames
            if (
                verified.info.get("loop") != 0
                or output_frame_count < 2
                or output_frame_count > frame_count
                or sum(output_delays) != duration
                or min(output_delays, default=0) < MIN_FRAME_DELAY_MS
            ):
                raise CatalogPipelineError(
                    f"{item.catalog_id}: normalized animation metadata changed unexpectedly."
                )
        poster = _lossless_webp(frames[0])
        _metadata_is_stripped(poster)
        animation_hash = _sha256(animation)
        poster_hash = _sha256(poster)
        return {
            "width": image.width,
            "height": image.height,
            "frame_count": output_frame_count,
            "duration_ms": duration,
            "minimum_frame_delay_ms": min(output_delays),
            "asset": _prepared_object(
                catalog_id=item.catalog_id,
                version_sha256=animation_hash,
                content_sha256=animation_hash,
                filename="animation.gif",
                content_type=CONTENT_TYPES["animated"],
                body=animation,
            ),
            "poster": _prepared_object(
                catalog_id=item.catalog_id,
                version_sha256=animation_hash,
                content_sha256=poster_hash,
                filename="poster.webp",
                content_type=CONTENT_TYPES["poster"],
                body=poster,
            ),
            "poster_sha256": poster_hash,
        }
    finally:
        for frame in frames:
            frame.close()
        image.close()


def _write_immutable(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != body:
            raise CatalogPipelineError(f"Refusing to overwrite non-matching output {path}.")
        return
    try:
        with path.open("xb") as output:
            output.write(body)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != body:
            raise CatalogPipelineError(f"Concurrent output differs at {path}.") from None


def _object_record(value: PreparedObject) -> dict[str, Any]:
    return {
        "relative_path": value.relative_path,
        "storage_key": value.storage_key,
        "sha256": value.sha256,
        "size": value.size,
        "content_type": value.content_type,
        "cache_control": IMMUTABLE_CACHE_CONTROL,
    }


def prepare_catalog(
    *,
    manifest_path: Path,
    source_root: Path,
    output_root: Path,
    reuse_attestation_path: Path | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    existing = (
        load_attestation(reuse_attestation_path, expected_manifest=None)
        if reuse_attestation_path
        else None
    )
    existing_by_id = {item["catalog_id"]: item for item in existing["items"]} if existing else {}
    records: list[dict[str, Any]] = []
    for item in manifest.items:
        source_path = _checked_source(source_root, item.source_path)
        source_size = source_path.stat().st_size
        if source_size > MAX_SOURCE_BYTES:
            raise CatalogPipelineError(
                f"{item.catalog_id}: source is {source_size} bytes; limit is {MAX_SOURCE_BYTES}."
            )
        source = source_path.read_bytes()
        if _sha256(source) != item.source_sha256:
            raise CatalogPipelineError(f"{item.catalog_id}: source SHA-256 mismatch.")
        detected_format = _detect_format(source)
        _validate_exact_container(source, detected_format)

        previous = existing_by_id.get(item.catalog_id)
        if previous is not None:
            if previous["source_sha256"] != item.source_sha256 or previous["kind"] != item.kind:
                raise CatalogPipelineError(
                    f"{item.catalog_id}: a reused attestation has different source identity."
                )
            objects = [previous["asset"]]
            if previous["poster"] is not None:
                objects.append(previous["poster"])
            for object_record in objects:
                object_path = reuse_attestation_path.parent / object_record["relative_path"]
                body = object_path.read_bytes()
                if len(body) != object_record["size"] or _sha256(body) != object_record["sha256"]:
                    raise CatalogPipelineError(
                        f"{item.catalog_id}: reused prepared object does not match attestation."
                    )
                _write_immutable(output_root / object_record["relative_path"], body)
            normalized = {
                "width": previous["width"],
                "height": previous["height"],
                "frame_count": previous["frame_count"],
                "duration_ms": previous["duration_ms"],
                "minimum_frame_delay_ms": previous["minimum_frame_delay_ms"],
                "asset": PreparedObject(
                    relative_path=previous["asset"]["relative_path"],
                    storage_key=previous["asset"]["storage_key"],
                    sha256=previous["asset"]["sha256"],
                    size=previous["asset"]["size"],
                    content_type=previous["asset"]["content_type"],
                    body=(
                        reuse_attestation_path.parent / previous["asset"]["relative_path"]
                    ).read_bytes(),
                ),
                "poster": (
                    PreparedObject(
                        relative_path=previous["poster"]["relative_path"],
                        storage_key=previous["poster"]["storage_key"],
                        sha256=previous["poster"]["sha256"],
                        size=previous["poster"]["size"],
                        content_type=previous["poster"]["content_type"],
                        body=(
                            reuse_attestation_path.parent / previous["poster"]["relative_path"]
                        ).read_bytes(),
                    )
                    if previous["poster"]
                    else None
                ),
                "poster_sha256": previous["poster_sha256"],
            }
        elif item.kind == "static":
            normalized = _normalize_static(item, source, detected_format)
        else:
            normalized = _normalize_animated(item, source, detected_format)

        asset: PreparedObject = normalized["asset"]
        poster: PreparedObject | None = normalized["poster"]
        _write_immutable(output_root / asset.relative_path, asset.body)
        if poster is not None:
            _write_immutable(output_root / poster.relative_path, poster.body)
        records.append(
            {
                "catalog_id": item.catalog_id,
                "source_path": item.source_path,
                "source_sha256": item.source_sha256,
                "detected_source_format": detected_format,
                "display_name": item.display_name,
                "accessibility_label": item.accessibility_label,
                "kind": item.kind,
                "ordering": item.ordering,
                "enabled": item.enabled,
                "selectable": item.selectable,
                "quick_order": item.quick_order,
                "provenance_source": item.provenance_source,
                "provenance_author": item.provenance_author,
                "license": item.license,
                "rights_basis": item.rights_basis,
                "approval_status": item.approval_status,
                "width": normalized["width"],
                "height": normalized["height"],
                "frame_count": normalized["frame_count"],
                "duration_ms": normalized["duration_ms"],
                "minimum_frame_delay_ms": normalized["minimum_frame_delay_ms"],
                "immutable_asset_version": f"sha256-{asset.sha256}",
                "asset": _object_record(asset),
                "poster": _object_record(poster) if poster else None,
                "poster_sha256": normalized.get("poster_sha256", ""),
            }
        )
    attestation = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "manifest_sha256": manifest.sha256,
        "catalog_id": manifest.catalog_id,
        "catalog_version": manifest.catalog_version,
        "approval_scope": manifest.approval_scope,
        "quick_reactions": list(manifest.quick_reactions),
        "limits": {
            "source_bytes": MAX_SOURCE_BYTES,
            "output_bytes": MAX_OUTPUT_BYTES,
            "dimension": MAX_DIMENSION,
            "frame_count": MAX_FRAME_COUNT,
            "duration_ms": MAX_DURATION_MS,
            "decoded_rgba_bytes": MAX_DECODED_RGBA_BYTES,
            "minimum_frame_delay_ms": MIN_FRAME_DELAY_MS,
        },
        "items": records,
    }
    attestation_body = _canonical_json(attestation)
    attestation_path = output_root / "reaction-catalog-attestation.json"
    _write_immutable(attestation_path, attestation_body)
    return attestation_path, _sha256(attestation_body), attestation


def load_attestation(path: Path, *, expected_manifest: CatalogManifest | None) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = _expect_object(json.loads(raw), where="attestation")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CatalogPipelineError("Attestation must be readable UTF-8 JSON.") from error
    if document.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        raise CatalogPipelineError("Unsupported attestation schema.")
    if document.get("normalizer_version") != NORMALIZER_VERSION:
        raise CatalogPipelineError("Attestation normalizer version does not match.")
    if expected_manifest is not None:
        if document.get("manifest_sha256") != expected_manifest.sha256:
            raise CatalogPipelineError("Attestation does not match the exact manifest bytes.")
        if document.get("catalog_id") != expected_manifest.catalog_id:
            raise CatalogPipelineError("Attestation catalog ID does not match.")
        manifest_ids = [item.catalog_id for item in expected_manifest.items]
        attested_ids = [
            item.get("catalog_id") for item in document.get("items", []) if isinstance(item, dict)
        ]
        if attested_ids != manifest_ids:
            raise CatalogPipelineError("Attestation item order/allowlist does not match manifest.")
    canonical = _canonical_json(document)
    if canonical != raw:
        raise CatalogPipelineError("Attestation is not canonical or has been reformatted.")
    return document


def load_prepared_objects(*, attestation_path: Path, item: dict[str, Any]) -> list[PreparedObject]:
    result = []
    for label in ("asset", "poster"):
        value = item.get(label)
        if value is None:
            continue
        record = _expect_object(value, where=f"{item.get('catalog_id')}.{label}")
        expected_keys = {
            "relative_path",
            "storage_key",
            "sha256",
            "size",
            "content_type",
            "cache_control",
        }
        _expect_exact_keys(record, expected_keys, where=f"{item.get('catalog_id')}.{label}")
        relative = _relative_source_path(
            record["relative_path"], where=f"{item.get('catalog_id')}.{label}.relative_path"
        )
        path = attestation_path.parent / relative
        if path.is_symlink():
            raise CatalogPipelineError(f"Prepared object cannot be a symlink: {relative}.")
        body = path.read_bytes()
        if (
            not SHA256.fullmatch(str(record["sha256"]))
            or record["size"] != len(body)
            or record["sha256"] != _sha256(body)
            or record["cache_control"] != IMMUTABLE_CACHE_CONTROL
        ):
            raise CatalogPipelineError(f"Prepared object does not match attestation: {relative}.")
        if record["content_type"] not in CONTENT_TYPES.values():
            raise CatalogPipelineError(f"Prepared object has invalid Content-Type: {relative}.")
        result.append(
            PreparedObject(
                relative_path=relative,
                storage_key=record["storage_key"],
                sha256=record["sha256"],
                size=record["size"],
                content_type=record["content_type"],
                body=body,
            )
        )
    return result


def sync_catalog(
    *,
    manifest_path: Path,
    attestation_path: Path,
    environment: str,
    object_store: ReactionObjectStore,
    imported_at,
    activate: bool,
) -> dict[str, Any]:
    from django.db import transaction

    from apps.discussions.models import ReactionCatalogItem, ReactionSettings

    if environment not in {"staging", "production"}:
        raise CatalogPipelineError("environment must be staging or production.")
    if object_store.environment != environment:
        raise CatalogPipelineError("Object-store prefix does not match requested environment.")
    manifest = load_manifest(manifest_path)
    if environment == "production" and (
        manifest.approval_scope != "production-approved"
        or any(item.approval_status != "production-approved" for item in manifest.items)
    ):
        raise CatalogPipelineError(
            "Production sync is fail-closed for staging-only or unverified assets."
        )
    attestation = load_attestation(attestation_path, expected_manifest=manifest)
    attested_by_id = {item["catalog_id"]: item for item in attestation["items"]}
    verified_object_count = 0
    for manifest_item in manifest.items:
        attested = attested_by_id[manifest_item.catalog_id]
        for prepared in load_prepared_objects(attestation_path=attestation_path, item=attested):
            object_store.put_if_absent(
                prepared,
                catalog_id=manifest_item.catalog_id,
                version=attested["immutable_asset_version"],
            )
            object_store.verify(
                prepared,
                catalog_id=manifest_item.catalog_id,
                version=attested["immutable_asset_version"],
            )
            verified_object_count += 1

    imported = 0
    updated = 0
    if activate:
        with transaction.atomic():
            desired_quick = {
                item.catalog_id: item.quick_order
                for item in manifest.items
                if item.quick_order is not None
            }
            current_quick = dict(
                ReactionCatalogItem.objects.filter(quick_order__isnull=False).values_list(
                    "catalog_id", "quick_order"
                )
            )
            if current_quick != desired_quick:
                ReactionCatalogItem.objects.filter(quick_order__isnull=False).update(
                    quick_order=None
                )
            for manifest_item in manifest.items:
                attested = attested_by_id[manifest_item.catalog_id]
                defaults = {
                    "display_name": attested["display_name"],
                    "accessibility_label": attested["accessibility_label"],
                    "kind": attested["kind"],
                    "ordering": attested["ordering"],
                    "enabled": attested["enabled"],
                    "selectable": attested["selectable"],
                    "quick_order": attested["quick_order"],
                    "source_sha256": attested["source_sha256"],
                    "normalized_sha256": attested["asset"]["sha256"],
                    "poster_sha256": attested["poster_sha256"],
                    "immutable_asset_version": attested["immutable_asset_version"],
                    "intrinsic_width": attested["width"],
                    "intrinsic_height": attested["height"],
                    "frame_count": attested["frame_count"],
                    "duration_ms": attested["duration_ms"],
                    "minimum_frame_delay_ms": attested["minimum_frame_delay_ms"],
                    "asset_storage_key": attested["asset"]["storage_key"],
                    "poster_storage_key": (
                        attested["poster"]["storage_key"] if attested["poster"] else ""
                    ),
                    "provenance_source": attested["provenance_source"],
                    "provenance_author": attested["provenance_author"],
                    "license": attested["license"],
                    "rights_basis": attested["rights_basis"],
                    "approval_status": attested["approval_status"],
                    "manifest_sha256": manifest.sha256,
                    "imported_at": imported_at,
                }
                candidate = ReactionCatalogItem(catalog_id=manifest_item.catalog_id, **defaults)
                existing = ReactionCatalogItem.objects.filter(pk=manifest_item.catalog_id).first()
                if existing is None:
                    candidate.full_clean()
                    ReactionCatalogItem.objects.create(
                        catalog_id=manifest_item.catalog_id, **defaults
                    )
                    imported += 1
                else:
                    candidate.full_clean(validate_unique=False)
                    changed = any(
                        getattr(existing, field) != value
                        for field, value in defaults.items()
                        if field != "imported_at"
                    )
                    if changed:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                        updated += 1
            quick = [
                ReactionCatalogItem.objects.get(pk=catalog_id)
                for catalog_id in manifest.quick_reactions
            ]
            from wagtail.models import Site

            settings_rows = list(ReactionSettings.objects.select_for_update())
            configured_site_ids = {row.site_id for row in settings_rows}
            settings_rows.extend(
                ReactionSettings.for_site(site)
                for site in Site.objects.exclude(pk__in=configured_site_ids)
            )
            for settings_row in settings_rows:
                (
                    settings_row.quick_reaction_item_one,
                    settings_row.quick_reaction_item_two,
                    settings_row.quick_reaction_item_three,
                ) = quick
                settings_row.save()
    return {
        "environment": environment,
        "prefix": object_store.prefix,
        "manifest_sha256": manifest.sha256,
        "attestation_sha256": _sha256(attestation_path.read_bytes()),
        "items": len(manifest.items),
        "objects": verified_object_count,
        "created": imported,
        "updated": updated,
        "activated": activate,
    }


class S3ReactionObjectStore:
    def __init__(self, storage, *, environment: str):
        if environment not in {"staging", "production"}:
            raise CatalogPipelineError("environment must be staging or production.")
        required = ("bucket_name", "connection", "_normalize_name", "location")
        if any(not hasattr(storage, name) for name in required):
            raise CatalogPipelineError("Reaction sync requires the configured S3 storage.")
        location = storage.location.strip("/")
        if not location or location.split("/", 1)[0] != environment:
            raise CatalogPipelineError(
                f"S3 location {location!r} is not isolated for {environment!r}."
            )
        self.storage = storage
        self.environment = environment
        self.prefix = location
        self.client = storage.connection.meta.client

    def _full_key(self, storage_key: str) -> str:
        return self.storage._normalize_name(storage_key)

    def _head(self, storage_key: str) -> dict[str, Any] | None:
        from botocore.exceptions import ClientError

        try:
            return self.client.head_object(
                Bucket=self.storage.bucket_name,
                Key=self._full_key(storage_key),
            )
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404 or error.response.get("Error", {}).get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return None
            raise

    def put_if_absent(self, item: PreparedObject, *, catalog_id: str, version: str) -> None:
        if self._head(item.storage_key) is not None:
            return
        checksum = base64.b64encode(bytes.fromhex(item.sha256)).decode()
        metadata = {
            "sha256": item.sha256,
            "catalog-id": catalog_id,
            "asset-version": version,
        }
        try:
            self.client.put_object(
                Bucket=self.storage.bucket_name,
                Key=self._full_key(item.storage_key),
                Body=item.body,
                ContentLength=item.size,
                ContentType=item.content_type,
                CacheControl=IMMUTABLE_CACHE_CONTROL,
                Metadata=metadata,
                ChecksumSHA256=checksum,
                IfNoneMatch="*",
            )
        except Exception:
            if self._head(item.storage_key) is None:
                raise

    def verify(self, item: PreparedObject, *, catalog_id: str, version: str) -> None:
        head = self._head(item.storage_key)
        if head is None:
            raise CatalogPipelineError(f"Uploaded object is missing: {item.storage_key}.")
        expected_metadata = {
            "sha256": item.sha256,
            "catalog-id": catalog_id,
            "asset-version": version,
        }
        actual_metadata = {
            str(key).lower(): value for key, value in head.get("Metadata", {}).items()
        }
        if (
            head.get("ContentLength") != item.size
            or head.get("ContentType") != item.content_type
            or head.get("CacheControl") != IMMUTABLE_CACHE_CONTROL
            or any(actual_metadata.get(key) != value for key, value in expected_metadata.items())
        ):
            raise CatalogPipelineError(f"Object headers do not match: {item.storage_key}.")
        response = self.client.get_object(
            Bucket=self.storage.bucket_name,
            Key=self._full_key(item.storage_key),
        )
        body = response["Body"].read(MAX_OUTPUT_BYTES + 1)
        if len(body) != item.size or _sha256(body) != item.sha256 or body != item.body:
            raise CatalogPipelineError(f"Object bytes do not match: {item.storage_key}.")
