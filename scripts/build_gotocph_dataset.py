"""Build the structured GOTO Copenhagen dataset under data/gotocph/.

Input is the extraction output directory (one folder per edition holding
sessions.json, sessions_todo.json and optionally speakers.json). Output:

    data/gotocph/
        index.json                      # editions, talk counts, speaker count
        <year>/index.json               # talk summaries for that edition
        <year>/<talk-slug>/talk.json    # title, abstract, speakers, slide URL
        <year>/<talk-slug>/slides.pdf   # with --download, when slides exist
        speakers/<speaker-slug>.json    # name, role, bio, links, talks

Talks still listed in sessions_todo.json get a stub talk.json with
"extracted": false so every scheduled talk has a folder.

Usage:
    python scripts/build_gotocph_dataset.py /path/to/dataset/gotocph [--download]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any, TypeAlias

ROOT = Path(__file__).resolve().parent.parent / "data" / "gotocph"
# A JSON object from the extraction output or the dataset written from it
Record: TypeAlias = dict[str, Any]
ORGANIZATION = {"slug": "gotocph", "name": "GOTO Copenhagen", "url": "https://gotocph.com"}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80].rstrip("-")


def url_id(url: str | None) -> int | None:
    m = re.search(r"/(\d+)(?:/|$)", url or "")
    return int(m.group(1)) if m else None


def talk_slug(session: Record) -> str:
    # gotocph session URLs end in a readable slug: /<year>/sessions/<id>/<slug>
    tail = (session.get("session_url") or "").rstrip("/").rsplit("/", 1)[-1]
    if tail and not tail.isdigit():
        return slugify(tail)
    return slugify(session.get("title") or str(session["session_id"]))


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "orgestra-dataset/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"  ! {url}: {exc}", file=sys.stderr)
        return False
    dest.write_bytes(data)
    return True


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def unique_slugs(sessions: list[Record]) -> list[str]:
    # Recurring sessions (e.g. "Extended Keynote Q&A") share a URL slug; suffix their id
    slugs = [talk_slug(s) for s in sessions]
    counts = Counter(slugs)
    return [
        f"{slug}-{s['session_id']}" if counts[slug] > 1 else slug
        for slug, s in zip(slugs, sessions, strict=True)
    ]


def new_talk(session: Record, *, extracted: bool, year: int, slug: str) -> Record:
    return {
        "slug": slug,
        "organization": ORGANIZATION["slug"],
        "year": year,
        "session_id": session["session_id"],
        "extracted": extracted,
        "title": session.get("title"),
        "section": session.get("section"),
        "format": session.get("format"),
        "track": session.get("track"),
        "tags": session.get("tags") or [],
        "day": session.get("day"),
        "start": session.get("start"),
        "end": session.get("end"),
        "room": session.get("room"),
        "abstract": session.get("abstract"),
        "speakers": [],
        "session_url": session.get("session_url"),
        "video_url": session.get("video_url"),
        "other_links": session.get("other_links") or [],
        "slides_url": session.get("slides_url"),
        "slides_file": None,
    }


def add_speakers(
    talk: Record, session: Record, *, bios: dict[int | None, Record], speakers: dict[str, Record]
) -> None:
    year = talk["year"]
    for sp in session.get("speakers") or []:
        sp_slug = slugify(sp["name"])
        bio = bios.get(url_id(sp.get("url")), {})
        entry = speakers.setdefault(
            sp_slug,
            {
                "slug": sp_slug,
                "name": sp["name"],
                "role_company": sp.get("role_company"),
                "role": bio.get("role"),
                "company": bio.get("company"),
                "bio": bio.get("bio"),
                "email": bio.get("email"),
                "photo_url": bio.get("photo_url"),
                "links": bio.get("links") or {},
                "profiles": {},
                "talks": [],
            },
        )
        if sp.get("url"):
            entry["profiles"][str(year)] = sp["url"]
        entry["talks"].append(f"{year}/{talk['slug']}")
        talk["speakers"].append({"slug": sp_slug, "name": sp["name"], "role_company": sp.get("role_company")})


def attach_slides(talk: Record, talk_dir: Path, fetch: bool) -> None:
    if not talk["slides_url"]:
        return
    name = talk["slides_url"].split("?")[0]
    dest = talk_dir / f"slides{Path(name).suffix.lower() or '.pdf'}"
    talk_dir.mkdir(parents=True, exist_ok=True)
    if (fetch and download(talk["slides_url"], dest)) or dest.exists():
        talk["slides_file"] = dest.name


def summarize(talk: Record) -> Record:
    return {
        "slug": talk["slug"],
        "session_id": talk["session_id"],
        "title": talk["title"],
        "speakers": [s["name"] for s in talk["speakers"]],
        "extracted": talk["extracted"],
        "slides_url": talk["slides_url"],
        "slides_file": talk["slides_file"],
    }


def build_edition(year_dir: Path, fetch: bool, speakers: dict[str, Record]) -> Record:
    year = int(year_dir.name)
    done = load(year_dir / "sessions.json", {}).get("sessions", [])
    todo = load(year_dir / "sessions_todo.json", [])
    bios = {
        s.get("speaker_id") or url_id(s.get("speaker_url")): s for s in load(year_dir / "speakers.json", [])
    }
    extracted_flags = [True] * len(done) + [False] * len(todo)
    sessions = done + todo
    index = []
    for session, extracted, slug in zip(sessions, extracted_flags, unique_slugs(sessions), strict=True):
        talk = new_talk(session, extracted=extracted, year=year, slug=slug)
        add_speakers(talk, session, bios=bios, speakers=speakers)
        talk_dir = ROOT / str(year) / slug
        attach_slides(talk, talk_dir, fetch)
        write_json(talk_dir / "talk.json", talk)
        index.append(summarize(talk))
    index.sort(key=itemgetter("session_id"))
    write_json(ROOT / str(year) / "index.json", {"year": year, "talks": index})
    return {
        "year": year,
        "talks": len(index),
        "extracted": sum(t["extracted"] for t in index),
        "slides_known": sum(bool(t["slides_url"]) for t in index),
        "slides_downloaded": sum(bool(t["slides_file"]) for t in index),
    }


def build(src: Path, fetch: bool) -> None:
    speakers: dict[str, Record] = {}
    editions = []
    for year_dir in sorted(p for p in src.iterdir() if p.is_dir() and p.name.isdigit()):
        stats = build_edition(year_dir, fetch, speakers)
        editions.append(stats)
        print(stats)
    for slug, s in speakers.items():
        write_json(ROOT / "speakers" / f"{slug}.json", s)
    write_json(ROOT / "index.json", {**ORGANIZATION, "editions": editions, "speakers": len(speakers)})
    print(f"{len(speakers)} speakers")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("source", type=Path, help="extraction output dir with <year>/ folders")
    p.add_argument("--download", action="store_true", help="fetch slide files")
    args = p.parse_args()
    build(args.source, args.download)


if __name__ == "__main__":
    main()
