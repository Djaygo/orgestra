"""Download the slide decks listed in data/<organization>/<year>/<slug>/talk.json.

Each real `slides_url` (http or https, not the "__PENDING__" placeholder) is saved as `slides.pdf` next
to its talk.json and recorded as `"slides_file"` in talk.json, in the year's index.json and in the
edition's `slides_downloaded` count. Decks that are already downloaded are left alone, so re-running is
cheap, and a response that is not a PDF is reported and not saved.

Usage:
    python scripts/fetch_slides.py [data-dir]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import attrs

PDF_MAGIC = b"%PDF"
DECK = "slides.pdf"
Record = dict[str, Any]


@attrs.frozen
class Report:
    downloaded: list[str]
    failed: list[str]


def http_fetch(url: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - http(s) URLs from our dataset, checked by the caller
        url, headers={"User-Agent": "orgestra-dataset/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - http(s) URLs from our dataset
        return response.read()


def read_json(path: Path) -> Record:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Record) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_deck(talk_path: Path) -> None:
    talk = read_json(talk_path)
    if talk.get("slides_file") != DECK:
        write_json(talk_path, talk | {"slides_file": DECK})


def refresh_indexes(organization_dir: Path) -> None:
    """Make the year indexes and the edition counts agree with the decks on disk."""
    organization_path = organization_dir / "index.json"
    organization = read_json(organization_path)
    for edition in organization.get("editions", []):
        year_path = organization_dir / str(edition["year"]) / "index.json"
        if not year_path.exists():
            continue
        year = read_json(year_path)
        for entry in year["talks"]:
            if (year_path.parent / entry["slug"] / DECK).exists():
                entry["slides_file"] = DECK
        edition["slides_downloaded"] = sum(1 for entry in year["talks"] if entry.get("slides_file"))
        write_json(year_path, year)
    write_json(organization_path, organization)


def fetch_slides(data_dir: Path, fetch: Callable[[str], bytes] = http_fetch) -> Report:
    downloaded: list[str] = []
    failed: list[str] = []
    for talk_path in sorted(data_dir.glob("*/*/*/talk.json")):
        talk = read_json(talk_path)
        url = talk.get("slides_url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        deck = talk_path.with_name(DECK)
        ref = f"{talk['year']}/{talk['slug']}"
        if not deck.exists():
            try:
                data = fetch(url)
            except Exception as error:  # any failure of one deck must not stop the others
                failed.append(f"{ref}: {error}")
                continue
            if not data.startswith(PDF_MAGIC):
                failed.append(f"{ref}: not a PDF")
                continue
            deck.write_bytes(data)
            downloaded.append(ref)
        record_deck(talk_path)
    for organization_dir in sorted(path.parent for path in data_dir.glob("*/index.json")):
        refresh_indexes(organization_dir)
    return Report(downloaded=downloaded, failed=failed)


def main() -> None:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data"
    report = fetch_slides(data_dir)
    print(f"{len(report.downloaded)} downloaded")
    for failure in report.failed:
        print(f"  ! {failure}", file=sys.stderr)


if __name__ == "__main__":
    main()
