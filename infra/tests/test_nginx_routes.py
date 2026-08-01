from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_SUFFIXES = (
    "logout/",
    "signup/",
    "login/",
    "verify-email/",
    "verify-email/resend/",
    "password/reset/",
    "password/reset/confirm/",
    "password/set/",
    "password/change/",
    "profile/",
)
AUTH_ROUTES = tuple(f"/api/auth/{suffix}" for suffix in AUTH_SUFFIXES) + tuple(
    f"/api/v1/auth/{suffix}" for suffix in AUTH_SUFFIXES
)


def config(name):
    return (ROOT / "infra" / "nginx" / "conf.d" / name).read_text()


def test_exact_frontend_api_exceptions_precede_django_api_prefixes():
    for name in ("production.conf", "staging.conf"):
        contents = config(name)
        for route in ("/api/draft", "/api/draft/disable", "/api/revalidate"):
            assert f"location = {route} " in contents
        assert contents.index("location = /api/revalidate") < contents.index(
            "location ^~ /api/v1/"
        )
        for suffix in AUTH_SUFFIXES:
            assert contents.index(
                f"location = /api/v1/auth/{suffix}"
            ) < contents.index("location ^~ /api/v1/")


def test_django_and_static_routes_are_explicit():
    for name in ("production.conf", "staging.conf"):
        contents = config(name)
        for route in (
            "/api/health/",
            "/api/readiness/",
            "/api/me/",
            *AUTH_ROUTES,
        ):
            assert f"location = {route} " in contents
        for prefix in (
            "/api/v1/",
            "/accounts/",
            "/cms/",
            "/django-admin/",
            "/media/",
        ):
            assert prefix in contents
        assert "location /static/" in contents
        assert "proxy_pass http://" in contents
        assert "location ^~ /api/" in contents
        assert "location ^~ /api/auth/" not in contents
        assert "location ^~ /api/v1/auth/" not in contents
        assert "location ^~ /media/" in contents
        assert "return 404;" in contents


def test_account_mutations_have_bounded_json_edge_errors():
    for name in ("production.conf", "staging.conf"):
        contents = config(name)
        for route in AUTH_ROUTES:
            block = contents[contents.index(f"location = {route} ") :]
            block = block[: block.index("\n    }")]
            assert "client_max_body_size 16k;" in block
            assert "proxy_request_buffering on;" in block
            assert "error_page 413 = @auth_api_body_too_large;" in block
        handler = contents[contents.index("location @auth_api_body_too_large ") :]
        handler = handler[: handler.index("\n    }")]
        assert "internal;" in handler
        assert "client_max_body_size 0;" in handler
        assert "default_type application/json;" in handler
        assert 'add_header Cache-Control "private, no-store" always;' in handler
        assert 'add_header Vary "Cookie" always;' in handler
        assert "return 413" in handler


def test_staging_auth_exceptions_are_narrow():
    contents = config("staging.conf")
    assert 'auth_basic "Staging"' in contents
    assert "location ^~ /.well-known/acme-challenge/" in contents
    webhook = contents[contents.index("location = /api/v1/email/webhooks/resend/") :]
    webhook = webhook[: webhook.index("\n    }")]
    assert "auth_basic off;" in webhook
    assert "proxy_request_buffering on;" in webhook


def test_forwarding_chain_is_replaced_not_appended():
    proxy = (ROOT / "infra" / "nginx" / "snippets" / "proxy.conf").read_text()
    assert "X-Forwarded-For $remote_addr" in proxy
    assert "$proxy_add_x_forwarded_for" not in proxy
    for header in (
        "Host $host",
        "X-Forwarded-Host $host",
        "X-Forwarded-Proto $upstream_forwarded_proto",
        "X-Real-IP $remote_addr",
    ):
        assert header in proxy


def test_live_upstreams_use_dynamic_docker_dns_and_isolated_zones():
    nginx = (ROOT / "infra" / "nginx" / "nginx.conf").read_text()
    assert "resolver 127.0.0.11" in nginx
    assert "resolver_timeout 2s;" in nginx
    zones = set()
    for environment in ("staging", "production"):
        contents = config(f"{environment}.conf")
        for service in ("django", "next"):
            alias = f"{environment}-{service}"
            zone = f"{environment}_{service}_zone"
            assert f"zone {zone} 64k;" in contents
            assert f"server {alias}:" in contents
            assert " resolve;" in contents
            zones.add(zone)
    assert len(zones) == 4


def test_missing_upstreams_have_bounded_failure():
    proxy = (ROOT / "infra" / "nginx" / "snippets" / "proxy.conf").read_text()
    assert "proxy_connect_timeout 3s;" in proxy
    assert "proxy_next_upstream_tries 1;" in proxy
