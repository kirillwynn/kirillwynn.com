#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


staging = load(sys.argv[1])
production = load(sys.argv[2])

assert staging["name"] == "kirillwynn-staging"
assert production["name"] == "kirillwynn-production"
assert staging["name"] != production["name"]

for document in (staging, production):
    assert set(document["services"]) == {"postgres", "django", "next", "worker"}
    for service in document["services"].values():
        assert "container_name" not in service
        assert not service.get("ports")
        image = service["image"]
        assert "@sha256:" in image
        assert ":latest" not in image

assert staging["networks"]["edge"]["name"] == "kirillwynn-staging-edge"
assert production["networks"]["edge"]["name"] == "kirillwynn-production-edge"
assert staging["networks"]["egress"]["name"] == "kirillwynn-staging-egress"
assert production["networks"]["egress"]["name"] == "kirillwynn-production-egress"
assert (
    staging["networks"]["application"]["name"]
    != production["networks"]["application"]["name"]
)
assert (
    staging["networks"]["database"]["name"]
    != production["networks"]["database"]["name"]
)
assert (
    staging["volumes"]["postgres_data"]["name"]
    != production["volumes"]["postgres_data"]["name"]
)
assert (
    staging["volumes"]["next_cache"]["name"]
    != production["volumes"]["next_cache"]["name"]
)

staging_postgres = staging["services"]["postgres"]["environment"]
production_postgres = production["services"]["postgres"]["environment"]
assert staging_postgres["POSTGRES_DB"] != production_postgres["POSTGRES_DB"]
assert staging_postgres["POSTGRES_USER"] != production_postgres["POSTGRES_USER"]

for document in (staging, production):
    services = document["services"]
    assert set(services["postgres"]["networks"]) == {"database"}
    assert set(services["worker"]["networks"]) == {
        "application",
        "database",
        "egress",
    }
    assert set(services["django"]["networks"]) == {
        "application",
        "database",
        "egress",
        "edge",
    }
    assert set(services["next"]["networks"]) == {"application", "egress", "edge"}
    assert document["networks"]["database"]["internal"] is True
    assert document["networks"]["application"]["internal"] is True
    assert "edge" not in services["worker"]["networks"]
    assert set(services["postgres"]["environment"]) == {
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    }
    assert set(services["next"]["environment"]) == {
        "PUBLIC_SITE_URL",
        "DJANGO_API_URL",
        "REVALIDATION_SECRET",
    }
