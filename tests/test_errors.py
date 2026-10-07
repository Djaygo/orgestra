import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app

BROWSER = {"accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def app(tmp_path):
    app = create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db"))

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def test_a_browser_gets_a_branded_404_with_a_way_forward(client):
    response = client.get("/talks/2025/nope", headers=BROWSER)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "Page not found" in response.text
    assert 'id="q"' in response.text
    assert 'href="/search?q=' in response.text
    assert 'href="/"' in response.text


def test_an_unknown_path_is_branded_too(client):
    response = client.get("/no/such/page", headers=BROWSER)

    assert response.status_code == 404
    assert "Page not found" in response.text


def test_a_boosted_htmx_navigation_gets_the_html_page(client):
    response = client.get("/talks/2025/nope", headers={"HX-Request": "true", "HX-Boosted": "true"})

    assert response.status_code == 404
    assert "Page not found" in response.text


def test_other_clients_keep_the_json_answer(client):
    response = client.get("/talks/2025/nope", headers={"accept": "application/json"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Talk not found"}


def test_a_server_error_shows_a_friendly_page_without_the_exception(client):
    response = client.get("/boom", headers=BROWSER)

    assert response.status_code == 500
    assert "Something went wrong" in response.text
    assert "secret internal detail" not in response.text
    assert "RuntimeError" not in response.text


def test_a_plain_htmx_request_gets_the_html_page(client):
    response = client.get("/speakers/nope", headers={"HX-Request": "true"})

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


def test_a_server_error_keeps_json_for_api_clients_without_the_exception(client):
    response = client.get("/boom", headers={"accept": "application/json"})

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    assert "application/json" in response.headers["content-type"]
