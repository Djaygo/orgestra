"""Build the structured GOTO Copenhagen dataset under data/gotocph/.

Input is the extracted talk metadata (one JSON file per edition, a list of
talk objects). Output layout:

    data/gotocph/
        index.json                      # editions and talk counts
        <year>/index.json               # talk summaries for that edition
        <year>/<talk-slug>/talk.json    # title, abstract, speakers, slide URL
        <year>/<talk-slug>/slides.pdf   # with --download, when slides exist
        speakers/<speaker-slug>.json    # name, bio, links, talks

Usage:
    python scripts/build_gotocph_dataset.py 2025=talks_2025.json 2026=talks_2026.json [--download]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "gotocph"
ORGANIZATION = {"slug": "gotocph", "name": "GOTO Copenhagen", "url": "https://gotocph.com"}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80].rstrip("-")


def first(d: dict, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, "", []):
            return d[k]
    return default


def normalize_speaker(raw) -> dict:
    if isinstance(raw, str):
        raw = {"name": raw}
    name = first(raw, "name", "full_name", default="").strip()
    return {
        "slug": slugify(name),
        "name": name,
        "title": first(raw, "title", "job_title", "role"),
        "company": first(raw, "company", "organization", "affiliation"),
        "bio": first(raw, "bio", "biography", "about"),
        "email": first(raw, "email"),
        "photo_url": first(raw, "photo_url", "photo", "image", "avatar"),
        "profile_url": first(raw, "profile_url", "url", "page_url"),
        "links": first(raw, "links", "socials", default={}),
    }


def normalize_talk(raw: dict, year: int) -> dict:
    title = first(raw, "title", "name", default="").strip()
    speakers = [normalize_speaker(s) for s in first(raw, "speakers", default=[])]
    return {
        "slug": first(raw, "slug") or slugify(title),
        "organization": ORGANIZATION["slug"],
        "year": year,
        "title": title,
        "abstract": first(raw, "abstract", "description", "introduction", "intro"),
        "speakers": speakers,
        "track": first(raw, "track"),
        "level": first(raw, "level"),
        "tags": first(raw, "tags", "topics", default=[]),
        "start": first(raw, "start", "start_time", "date"),
        "end": first(raw, "end", "end_time"),
        "room": first(raw, "room", "location"),
        "talk_url": first(raw, "talk_url", "url", "session_url", "page_url"),
        "slides_url": first(raw, "slides_url", "slide_url", "slides", "pdf_url"),
        "video_url": first(raw, "video_url", "video", "youtube_url"),
    }


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "orgestra-dataset/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001 - report and continue with the rest
        print(f"  ! {url}: {exc}", file=sys.stderr)
        return False
    dest.write_bytes(data)
    return True


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def build(editions: dict[int, Path], fetch: bool) -> None:
    speakers: dict[str, dict] = {}
    summary = []
    for year, src in sorted(editions.items()):
        talks = json.loads(src.read_text())
        if isinstance(talks, dict):
            talks = first(talks, "talks", "sessions", default=[])
        index, seen = [], set()
        for raw in talks:
            talk = normalize_talk(raw, year)
            slug, n = talk["slug"], 2
            while talk["slug"] in seen:
                talk["slug"] = f"{slug}-{n}"
                n += 1
            seen.add(talk["slug"])
            talk_dir = ROOT / str(year) / talk["slug"]
            talk["slides_file"] = None
            if talk["slides_url"]:
                ext = Path(talk["slides_url"].split("?")[0]).suffix.lower() or ".pdf"
                dest = talk_dir / f"slides{ext}"
                talk_dir.mkdir(parents=True, exist_ok=True)
                if (fetch and download(talk["slides_url"], dest)) or dest.exists():
                    talk["slides_file"] = dest.name
            for s in talk["speakers"]:
                entry = speakers.setdefault(s["slug"], {**s, "talks": []})
                for k, v in s.items():
                    if not entry.get(k) and v:
                        entry[k] = v
                entry["talks"].append(f"{year}/{talk['slug']}")
            talk["speakers"] = [
                {"slug": s["slug"], "name": s["name"]} for s in talk["speakers"]
            ]
            write_json(talk_dir / "talk.json", talk)
            index.append(
                {
                    "slug": talk["slug"],
                    "title": talk["title"],
                    "speakers": [s["name"] for s in talk["speakers"]],
                    "has_slides": talk["slides_file"] is not None,
                }
            )
        write_json(ROOT / str(year) / "index.json", {"year": year, "talks": index})
        summary.append(
            {
                "year": year,
                "talks": len(index),
                "with_slides": sum(t["has_slides"] for t in index),
            }
        )
        print(f"{year}: {len(index)} talks, {summary[-1]['with_slides']} with slides")
    for slug, s in speakers.items():
        write_json(ROOT / "speakers" / f"{slug}.json", s)
    write_json(
        ROOT / "index.json",
        {**ORGANIZATION, "editions": summary, "speakers": len(speakers)},
    )
    print(f"{len(speakers)} speakers")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("editions", nargs="+", help="YEAR=path/to/talks.json")
    p.add_argument("--download", action="store_true", help="fetch slide files")
    args = p.parse_args()
    editions = {}
    for e in args.editions:
        year, path = e.split("=", 1)
        editions[int(year)] = Path(path)
    build(editions, args.download)


if __name__ == "__main__":
    main()
