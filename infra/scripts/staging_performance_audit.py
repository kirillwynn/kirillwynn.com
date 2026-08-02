#!/usr/bin/env python3
"""Measure bounded read-only PostgreSQL API work against a staging snapshot."""

import json
import statistics
import time

from django.db import connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.blog.services.visibility import public_blog_posts


def measure(client, path, parameters=None):
    samples = []
    query_counts = []
    response_sizes = []
    cache_control = None
    vary = None
    for _attempt in range(3):
        started = time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = client.get(
                path,
                parameters or {},
                secure=True,
                HTTP_HOST="staging.kirillwynn.com",
            )
        elapsed = (time.perf_counter() - started) * 1_000
        if response.status_code != 200:
            raise RuntimeError(f"read-only performance probe returned {response.status_code}")
        samples.append(round(elapsed, 3))
        query_counts.append(len(queries))
        response_sizes.append(len(response.content))
        cache_control = response.headers.get("Cache-Control")
        vary = response.headers.get("Vary")
    return {
        "query_counts": query_counts,
        "query_count_max": max(query_counts),
        "server_ms_samples": samples,
        "server_ms_median": round(statistics.median(samples), 3),
        "response_bytes_max": max(response_sizes),
        "cache_control": cache_control,
        "vary": vary,
    }


def build_report():
    posts = list(public_blog_posts()[:10])
    if not posts:
        raise RuntimeError("staging performance audit requires a public post")
    first = posts[0]
    first_tag = first.tags.order_by("slug").values_list("slug", flat=True).first()
    client = Client()
    probes = {
        "feed_page_1": measure(client, reverse("blog_api:post-list"), {"page": 1}),
        "feed_page_2": measure(client, reverse("blog_api:post-list"), {"page": 2}),
        "unicode_search": measure(
            client,
            reverse("blog_api:post-list"),
            {"q": "東京"},
        ),
        "post_detail": measure(
            client,
            reverse("blog_api:post-detail", kwargs={"slug": first.slug}),
        ),
        "tag_catalog": measure(client, reverse("blog_api:tag-list")),
        "comments": measure(
            client,
            reverse("discussions_api:post-comments", kwargs={"slug": first.slug}),
        ),
        "post_reactions_batch": measure(
            client,
            reverse("discussions_api:post-reaction-batch"),
            {"ids": ",".join(str(post.pk) for post in posts)},
        ),
    }
    if first_tag:
        probes["tag_filter"] = measure(
            client,
            reverse("blog_api:post-list"),
            {"tag": first_tag},
        )
    return {
        "schema": "stage18-staging-performance-audit/v1",
        "database": "restored-staging-snapshot",
        "sample_count": 3,
        "probes": probes,
    }


def main():
    if connection.vendor != "postgresql":
        raise SystemExit("Stage 18 performance audit requires PostgreSQL")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        report = build_report()
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))


main()
