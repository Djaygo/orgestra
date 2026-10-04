import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app

TALK = "2025/13-years-of-cryptocurrency-de-anonymization-and-counting"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=tmp_path / "test.db")))


def post_to_talk(client, **fields):
    data = {"kind": "comment", "name": "Ada", "body": "Hello"} | fields
    return client.post(f"/talks/{TALK}/posts", data=data, follow_redirects=False)


def test_post_redirects_to_the_talk_and_shows_up_there(client):
    response = post_to_talk(client, kind="question", body="Why does this scale?")

    assert response.status_code == 303
    assert response.headers["location"] == f"/talks/{TALK}#post-1"
    html = client.get(f"/talks/{TALK}").text
    assert "Why does this scale?" in html
    assert "Question" in html


def test_reply_edit_history_restore_and_answered(client):
    post_to_talk(client, kind="question", body="line one\nline two")
    client.post("/posts/1/replies", data={"name": "Bob", "body": "an answer"})
    client.post("/posts/1/edit", data={"name": "Cy", "body": "line one\nline 2"})
    client.post("/posts/1/answered")

    html = client.get(f"/talks/{TALK}").text
    assert "an answer" in html
    assert "(edited)" in html
    assert 'class="diff-del"' in html
    assert "Answered" in html

    client.post("/posts/1/restore/1", data={"name": "Di"})
    restored = client.get(f"/talks/{TALK}").text
    assert restored.count("restore this version") == 2  # three revisions, the newest is current


def test_markup_in_a_body_is_escaped(client):
    post_to_talk(client, body="<script>alert(1)</script> & more")

    html = client.get(f"/talks/{TALK}").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in html


@pytest.mark.parametrize("field", ["name", "body"])
def test_blank_fields_are_rejected_and_nothing_is_stored(client, field):
    response = post_to_talk(client, **{field: "   "})

    assert response.status_code == 422
    assert "Hello" not in client.get(f"/talks/{TALK}").text


def test_too_long_fields_are_rejected(client):
    assert post_to_talk(client, name="x" * 41).status_code == 422
    assert post_to_talk(client, body="x" * 5001).status_code == 422


def test_unknown_targets_are_404(client):
    form = {"name": "A", "body": "b"}
    assert client.post("/talks/2025/nope/posts", data={"kind": "comment", **form}).status_code == 404
    assert client.post("/posts/99/replies", data=form).status_code == 404
    assert client.post("/posts/99/edit", data=form).status_code == 404
    assert client.post("/posts/99/restore/1", data={"name": "A"}).status_code == 404
    assert client.post("/posts/99/answered").status_code == 404
    assert post_to_talk(client).status_code == 303
    assert client.post("/posts/1/restore/99", data={"name": "A"}).status_code == 404


def test_answered_on_a_comment_is_a_bad_request(client):
    post_to_talk(client)

    assert client.post("/posts/1/answered").status_code == 400


def test_a_non_ascii_name_survives_the_cookie(client):
    post_to_talk(client, name="Zoë Ünal")

    html = client.get(f"/talks/{TALK}").text
    assert 'name="name" value="Zoë Ünal"' in html


def test_discussion_forms_keep_the_scroll_position_when_boosted(client):
    # htmx scrolls to the top after a boosted swap unless the swap says `show:none`.
    html = client.get(f"/talks/{TALK}").text

    assert '<section class="discussion" id="discussion" hx-swap="outerHTML show:none">' in html
