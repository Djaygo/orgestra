"""A small data directory on disk (one organization, 2025, a few talks) for page tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from orgestra.app import Settings, create_app


def write_talk(root: Path, slug: str, **fields: Any) -> Path:
    folder = root / "conf" / "2025" / slug
    folder.mkdir(parents=True)
    talk = {
        "slug": slug,
        "organization": "conf",
        "year": 2025,
        "session_id": abs(hash(slug)) % 10_000,
        "extracted": True,
        "title": slug.replace("-", " ").title(),
        "abstract": "A talk about something else.",
        "speakers": [],
        "session_url": f"https://example.com/{slug}",
    } | fields
    (folder / "talk.json").write_text(json.dumps(talk))
    return folder


def data_dir(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    (root / "conf").mkdir(parents=True)
    index = {"slug": "conf", "name": "Conf", "url": "https://example.com", "editions": []}
    (root / "conf" / "index.json").write_text(json.dumps(index))
    return root


def client_for(root: Path, tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=root, db_path=tmp_path / "test.db")))
