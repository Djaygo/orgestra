"""HTTP routes: full pages for navigation, HTML fragments for htmx, SSE for the conversations."""

from __future__ import annotations

import asyncio
import json
import os
import random
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Annotated

import attrs
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from orgestra.conversations import Conversation, Persona, conversations, personas
from orgestra.dataset import Catalog, load_catalog
from orgestra.discussion.models import db
from orgestra.events import SPOTLIGHT, Spotlight, hx_trigger
from orgestra.personas import initials, persona_hue
from orgestra.questions import summary
from orgestra.search import SearchIndex
from orgestra.thesaurus import load_thesaurus

PACKAGE_DIR = Path(__file__).parent
REPO_DATA_DIR = PACKAGE_DIR.parents[1] / "data"
SCENE_ENTRY = PACKAGE_DIR / "static" / "dist" / "stage.js"
SearchQuery = Annotated[str, Query(max_length=200)]


@attrs.frozen
class Settings:
    data_dir: Path = REPO_DATA_DIR
    db_path: Path = REPO_DATA_DIR / "orgestra.db"
    turn_interval_s: float = 3.5

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            data_dir=Path(os.environ.get("ORGESTRA_DATA_DIR", REPO_DATA_DIR)),
            db_path=Path(os.environ.get("ORGESTRA_DB_PATH", REPO_DATA_DIR / "orgestra.db")),
            turn_interval_s=float(os.environ.get("ORGESTRA_TURN_INTERVAL", "3.5")),
        )


@attrs.frozen
class Services:
    """Built once at startup and shared by every request through `app.state`."""

    settings: Settings
    catalog: Catalog
    index: SearchIndex
    cast: list[Persona]
    templates: Jinja2Templates


def is_fragment_request(request: Request) -> bool:
    """Whether htmx asked for a piece of the page (not a boosted link, which wants the whole page)."""
    return request.headers.get("HX-Request") == "true" and request.headers.get("HX-Boosted") != "true"


def cast_json(cast: list[Persona]) -> str:
    """The characters the stage draws, embedded in the page as JSON."""
    payload = [
        {
            "slug": p.speaker.slug,
            "name": p.speaker.name,
            "hue": persona_hue(p.speaker.slug),
            "talk": p.talk.ref,
        }
        for p in cast
    ]
    # Safe inside <script type="application/json">: no "</script>" can appear.
    return json.dumps(payload).replace("<", "\\u003c")


def sse_event(event: str, html: str) -> str:
    """One Server-Sent Event; every line of a multi-line payload needs its own `data:` prefix."""
    data = "\n".join(f"data: {line}" for line in html.splitlines() or [""])
    return f"event: {event}\n{data}\n\n"


def transcript_frames(script: Iterator[Conversation]) -> Iterator[Conversation]:
    """The transcript after each turn: the conversation so far, restarting with each new one."""
    for turns in script:
        for count in range(1, len(turns) + 1):
            yield turns[:count]


def build_templates(catalog: Catalog, cast: list[Persona]) -> Jinja2Templates:
    # What the layout (sidebar, stage) needs on every page.
    layout = {"catalog": catalog, "cast_json": cast_json(cast), "scene_available": SCENE_ENTRY.exists()}
    templates = Jinja2Templates(
        directory=PACKAGE_DIR / "templates", context_processors=[lambda _request: layout]
    )
    templates.env.filters.update(hue=persona_hue, initials=initials, summary=summary)
    return templates


def build_services(settings: Settings) -> Services:
    catalog = load_catalog(settings.data_dir)
    cast = personas(catalog)
    return Services(
        settings=settings,
        catalog=catalog,
        index=SearchIndex.build(catalog, load_thesaurus()),
        cast=cast,
        templates=build_templates(catalog, cast),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services


AppServices = Annotated[Services, Depends(get_services)]
router = APIRouter()


def search_response(request: Request, services: Services, query: str) -> HTMLResponse:
    result = services.index.search(query) if query.strip() else None
    if result is not None and is_fragment_request(request):
        response = services.templates.TemplateResponse(request, "partials/results.html", {"result": result})
        speakers = list(dict.fromkeys(s.slug for hit in result.hits for s in hit.talk.speakers))
        response.headers["HX-Trigger"] = hx_trigger(SPOTLIGHT, Spotlight(speakers=speakers))
        return response
    page = "search.html" if result is not None else "home.html"
    return services.templates.TemplateResponse(request, page, {"result": result})


@router.get("/", response_class=HTMLResponse)
def home(request: Request, services: AppServices, q: SearchQuery = "") -> HTMLResponse:
    return search_response(request, services, q)


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, services: AppServices, q: SearchQuery = "") -> HTMLResponse:
    return search_response(request, services, q)


@router.get("/lucky")
def lucky(services: AppServices) -> RedirectResponse:
    """A random talk with details, for the "I'm feeling curious" button."""
    talks = [talk for talk in services.catalog.talks.values() if talk.extracted]
    choice = random.choice(talks)  # ruff: ignore[S311] picks a talk to show, nothing secret
    return RedirectResponse(f"/talks/{choice.ref}", status_code=303)


@router.get("/talks/{year}/{slug}", response_class=HTMLResponse)
def talk(request: Request, services: AppServices, *, year: int, slug: str) -> HTMLResponse:
    found = services.catalog.talks.get(f"{year}/{slug}")
    if found is None:
        raise HTTPException(status_code=404, detail="Talk not found")
    context = {"talk": found, "questions": services.index.questions_for(found.ref)}
    return services.templates.TemplateResponse(request, "talk.html", context)


@router.get("/speakers/{slug}", response_class=HTMLResponse)
def speaker(request: Request, services: AppServices, slug: str) -> HTMLResponse:
    found = services.catalog.speakers.get(slug)
    if found is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    context = {"speaker": found, "talks": services.catalog.talks_of(found)}
    return services.templates.TemplateResponse(request, "speaker.html", context)


@router.get("/conversations/stream")
async def conversation_stream(request: Request, services: AppServices) -> StreamingResponse:
    """Endless SSE stream of `turn` events, each the transcript of the current conversation."""
    transcript = services.templates.get_template("partials/transcript.html")
    rng = random.Random()  # ruff: ignore[S311] picks who talks next, nothing secret

    async def events() -> AsyncIterator[str]:
        for turns in transcript_frames(conversations(services.cast, rng)):
            if await request.is_disconnected():
                return
            yield sse_event("turn", transcript.render(turns=turns))
            await asyncio.sleep(services.settings.turn_interval_s)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Orgestra")
    resolved = settings or Settings.from_env()
    resolved.db_path.parent.mkdir(parents=True, exist_ok=True)
    db.initialize(f"sqlite:///{resolved.db_path}")
    db.create_all()
    app.state.services = build_services(resolved)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.include_router(router)
    return app
