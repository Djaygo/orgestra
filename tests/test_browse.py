import re

import pytest

from tests.dirs import client_for, data_dir, write_speaker, write_talk


@pytest.fixture
def client(tmp_path):
    root = data_dir(tmp_path)
    ada = [{"slug": "ada", "name": "Ada Lovelace"}]
    write_talk(root, "old-keynote", year=2025, title="Old Keynote", section="Keynote", speakers=ada)
    write_talk(
        root,
        "media-talk",
        year=2025,
        title="Media Talk",
        video_url="https://www.youtube-nocookie.com/embed/abc",
        slides_url="https://x.test/a.pdf",
    )
    write_talk(root, "new-talk", year=2026, title="New Talk", speakers=ada)
    write_talk(root, "pending-talk", year=2026, extracted=False, title=None, abstract=None)
    write_speaker(root, "zed", name="Zed Zebra", role_company="Herder", talks=[])
    write_speaker(root, "ada", name="Ada Lovelace", talks=["2025/old-keynote", "2026/new-talk"])
    return client_for(root, tmp_path)


def rows(html: str) -> list[str]:
    return re.findall(r'class="browse-link" href="([^"]+)"', html)


def test_browse_lists_the_newest_year_first_by_default(client):
    html = client.get("/browse").text

    assert rows(html) == ["/talks/2026/new-talk", "/talks/2026/pending-talk"]
    assert re.search(r'aria-current="true"[^>]*>2026', html)


def test_a_year_tab_lists_that_years_talks_with_what_each_carries(client):
    html = client.get("/browse", params={"tab": "2025"}).text

    assert sorted(rows(html)) == ["/talks/2025/media-talk", "/talks/2025/old-keynote"]
    media = html.split("Media Talk")[1].split("</li>")[0]
    assert 'title="Video available"' in media
    assert 'title="Slides available"' in media


def test_the_speakers_tab_lists_everyone_by_name_with_their_talk_counts(client):
    html = client.get("/browse", params={"tab": "speakers"}).text

    assert rows(html) == ["/speakers/ada", "/speakers/zed"]
    assert "2 talks" in html
    assert "Herder" in html


@pytest.mark.parametrize("tab", ["1999", "nope", "<img src=x onerror=alert(1)>", "2025x", "²", "²⁰²⁵"])
def test_an_unknown_tab_falls_back_to_the_newest_year(client, tab):
    response = client.get("/browse", params={"tab": tab})

    assert response.status_code == 200
    assert rows(response.text) == ["/talks/2026/new-talk", "/talks/2026/pending-talk"]
    assert tab not in response.text


def test_the_list_can_be_filtered_in_the_browser(client):
    html = client.get("/browse").text

    assert 'data-filter-list="browse-list"' in html
    assert 'id="browse-list"' in html
    assert 'data-filter-text="new talk' in html


def test_browse_is_in_the_app_bar_of_every_page(client):
    for path in ("/", "/search?q=talk", "/talks/2025/old-keynote", "/browse"):
        assert re.search(r'class="action"\s+href="/browse"', client.get(path).text), path
