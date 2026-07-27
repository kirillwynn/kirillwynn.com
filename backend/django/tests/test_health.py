import pytest


def test_health_check_is_public_and_reports_ok(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_check_queries_database(client, django_assert_num_queries):
    with django_assert_num_queries(1):
        response = client.get("/api/readiness/")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_failure_is_bounded_and_does_not_expose_error(client, monkeypatch):
    from apps.core import views

    class BrokenConnection:
        def cursor(self):
            raise RuntimeError("credential-shaped internal detail")

    monkeypatch.setattr(views, "connection", BrokenConnection())
    response = client.get("/api/readiness/")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"credential-shaped" not in response.content
