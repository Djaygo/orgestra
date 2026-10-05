import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "fetch_slides.py"
_spec = importlib.util.spec_from_file_location("fetch_slides", SCRIPT)
assert _spec and _spec.loader
fetch_slides_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_slides_module)
fetch_slides = fetch_slides_module.fetch_slides

PDF = b"%PDF-1.4\n%fake deck"
REAL = "https://files.example.com/real.pdf"
HTML = "https://files.example.com/html.pdf"
RESPONSES = {REAL: PDF, HTML: b"<html>404 not found</html>"}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def data(tmp_path):
    org = tmp_path / "conf"
    editions = [{"year": 2025, "talks": 3, "slides_downloaded": 0}]
    write_json(org / "index.json", {"slug": "conf", "editions": editions})
    urls = {"real": REAL, "html": HTML, "pending": "__PENDING__"}
    entries = []
    for slug, url in urls.items():
        talk = {"slug": slug, "year": 2025, "slides_url": url, "slides_file": None}
        write_json(org / "2025" / slug / "talk.json", talk)
        entries.append({"slug": slug, "slides_url": url, "slides_file": None})
    write_json(org / "2025" / "index.json", {"year": 2025, "talks": entries})
    return tmp_path


class Downloader:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self.responses[url]


def test_downloads_real_decks_and_records_them(data):
    fetch = Downloader(RESPONSES)

    report = fetch_slides(data, fetch)

    assert report.downloaded == ["2025/real"]
    assert [failure.split(":")[0] for failure in report.failed] == ["2025/html"]
    assert (data / "conf/2025/real/slides.pdf").read_bytes() == PDF
    assert not (data / "conf/2025/html/slides.pdf").exists()
    assert json.loads((data / "conf/2025/real/talk.json").read_text())["slides_file"] == "slides.pdf"
    assert json.loads((data / "conf/2025/html/talk.json").read_text())["slides_file"] is None
    entries = {e["slug"]: e for e in json.loads((data / "conf/2025/index.json").read_text())["talks"]}
    assert entries["real"]["slides_file"] == "slides.pdf"
    assert entries["html"]["slides_file"] is None
    edition = json.loads((data / "conf/index.json").read_text())["editions"][0]
    assert edition["slides_downloaded"] == 1
    assert "__PENDING__" not in fetch.calls


def test_running_again_downloads_only_what_is_missing(data):
    fetch_slides(data, Downloader(RESPONSES))
    again = Downloader(RESPONSES)

    report = fetch_slides(data, again)

    assert report.downloaded == []
    assert again.calls == [HTML]


def test_a_failing_download_is_reported_and_does_not_stop_the_rest(data):
    def broken(url):
        if "real" in url:
            raise OSError("connection reset")
        return b"%PDF-1.4 ok"

    report = fetch_slides(data, broken)

    assert report.downloaded == ["2025/html"]
    assert report.failed == ["2025/real: connection reset"]
