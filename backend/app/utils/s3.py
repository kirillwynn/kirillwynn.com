"""
S3 helper utilities.

We use S3-compatible storage (TWC, MinIO, R2, AWS — doesn't matter as long as it's S3 API).
The app never exposes S3 credentials to clients.

Flow:
1) Admin requests a presigned PUT URL -> uploads directly to S3.
2) Admin commits the upload -> we verify metadata (HEAD) and mark asset as ready.
3) Public readers access /media/<id> -> app redirects to presigned GET URL.

Why redirect instead of embedding presigned GET in HTML?
- presigned URLs expire; stable /media/<id> does not.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


@lru_cache(maxsize=1)
def get_s3_client():
    """
    Create and cache a boto3 S3 client.

    We use caching to avoid creating a new client per request.
    This is safe because the client is thread-safe for typical usage.
    """
    endpoint_url = current_app.config["S3_ENDPOINT_URL"]
    region = current_app.config["S3_REGION"]
    access_key = current_app.config["S3_ACCESS_KEY_ID"]
    secret_key = current_app.config["S3_SECRET_ACCESS_KEY"]

    # Some S3-compatible providers need path-style addressing.
    # If yours works fine with virtual-host style, you can set this to False.
    address_style = current_app.config.get("S3_ADDRESSING_STYLE", "path")

    boto_cfg = BotoConfig(
        s3={"addressing_style": address_style},
        retries={"max_attempts": 5, "mode": "standard"},
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=boto_cfg,
    )


def presign_put(*, bucket: str, key: str, content_type: str, expires_in: int) -> str:
    """
    Create a presigned URL for uploading a single object with PUT.

    NOTE:
    - The client must upload using HTTP PUT to the returned URL.
    - The Content-Type must match what we sign here.
    """
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )


def presign_get(*, bucket: str, key: str, expires_in: int) -> str:
    """Create a presigned GET URL to read an object."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def head_object(*, bucket: str, key: str) -> dict[str, Any]:
    """Fetch object metadata from S3 (used to verify uploads on commit)."""
    s3 = get_s3_client()
    return s3.head_object(Bucket=bucket, Key=key)
