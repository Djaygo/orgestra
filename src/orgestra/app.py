"""HTTP routes: full pages for navigation, HTML fragments for htmx, SSE for the conversations."""

from __future__ import annotations

import asyncio
import json
import os
import random
from collections import Counter
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Annotated, TypeAlias

import attrs
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from orgestra.conversations import Conversation, Persona, conversations, personas
from orgestra.dataset import Catalog, load_catalog
from orgestra.discussion import routes as discussion_routes
from orgestra.discussion.diff import revision_history
from orgestra.discussion.models import db
from orgestra.discussion.render import ago, linkify
from orgestra.discussion.store import TalkStats, talk_stats, thread
from orgestra.events import SPOTLIGHT, Spotlight, hx_trigger
from orgestra.filters import Filters
from orgestra.highlight import highlight
from orgestra.personas import initials, persona_hue
from orgestra.questions import Question, summary
from orgestra.reports import routes as reports_routes
from orgestra.reports.build import build_tracker
from orgestra.reports.tracker import IssueTracker
from orgestra.search import Hit, SearchIndex, SearchResult
from orgestra.slides import load_slides
from orgestra.suggest import suggest
from orgestra.thesaurus import load_thesaurus

PACKAGE_DIR = Path(__file__).parent
REPO_DATA_DIR = PACKAGE_DIR.parents[1] / "data"
SCENE_ENTRY = PACKAGE_DIR / "static" / "dist" / "stage.js"
UI_ENTRY = PACKAGE_DIR / "static" / "dist" / "ui.js"
SearchQuery = Annotated[str, Query(max_length=200)]
FilterParam = Annotated[str, Query(max_length=10)]
RESULTS_SHOWN = 20
YearCount: TypeAlias = tuple[int, int]  # (year, number of hits)


@attrs.frozen
class Settings:
    data_dir: Path = REPO_DATA_DIR
    db_path: Path = REPO_DATA_DIR / "orgestra.db"
    turn_interval_s: float = 3.5
    issues_provider: str = "github"
    issues_repo: str = ""
    issues_token: str = attrs.field(default="", repr=False)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            data_dir=Path(os.environ.get("ORGESTRA_DATA_DIR", REPO_DATA_DIR)),
            db_path=Path(os.environ.get("ORGESTRA_DB_PATH", REPO_DATA_DIR / "orgestra.db")),
            turn_interval_s=float(os.environ.get("ORGESTRA_TURN_INTERVAL", "3.5")),
            issues_provider=os.environ.get("ORGESTRA_ISSUES_PROVIDER", "github"),
            issues_repo=os.environ.get("ORGESTRA_ISSUES_REPO", ""),
            issues_token=os.environ.get("ORGESTRA_ISSUES_TOKEN", ""),
        )


@attrs.frozen
class Services:
    """Built once at startup and shared by every request through `app.state`."""

    settings: Settings
    catalog: Catalog
    index: SearchIndex
    cast: list[Persona]
    templates: Jinja2Templates
    tracker: IssueTracker | None


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
    # What the layout (app bar, stage) needs on every page.
    layout = {
        "catalog": catalog,
        "cast_json": cast_json(cast),
        "scene_available": SCENE_ENTRY.exists(),
        "ui_available": UI_ENTRY.exists(),
    }

    def layout_context(request: Request) -> dict[str, object]:
        query = f"?{request.url.query}" if request.url.query else ""
        return layout | {
            # No button on the report pages themselves: it would link the form back to itself.
            "reports_enabled": request.app.state.services.tracker is not None
            and request.url.path != "/report",
            "report_from": request.url.path + query,
        }

    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates", context_processors=[layout_context])
    organization_names = {organization.slug: organization.name for organization in catalog.organizations}

    def organization_name(slug: str) -> str:
        return organization_names.get(slug, slug)

    templates.env.filters.update(
        highlight=highlight,
        org_name=organization_name,
        hue=persona_hue,
        initials=initials,
        summary=summary,
        ago=ago,
        linkify=linkify,
        history=revision_history,
    )
    return templates


def build_services(settings: Settings) -> Services:
    catalog = load_catalog(settings.data_dir)
    cast = personas(catalog)
    return Services(
        settings=settings,
        catalog=catalog,
        index=SearchIndex.build(catalog, load_thesaurus(), load_slides(settings.data_dir, catalog)),
        cast=cast,
        templates=build_templates(catalog, cast),
        tracker=build_tracker(settings.issues_provider, settings.issues_repo, settings.issues_token),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services


AppServices = Annotated[Services, Depends(get_services)]
router = APIRouter()


@attrs.frozen
class ResultsView:
    """What the results page shows: the filtered hits, and counts for the filter chips from all of them."""

    result: SearchResult
    filters: Filters
    hits: list[Hit]
    total: int
    year_counts: list[YearCount]
    slide_count: int
    video_count: int
    top_questions: list[Question]
    words: frozenset[str]
    stats: dict[str, TalkStats]
    popular_tags: list[str]


def results_view(services: Services, result: SearchResult, filters: Filters, session: Session) -> ResultsView:
    kept = [hit for hit in result.hits if filters.keeps(hit.talk)]
    shown = kept[:RESULTS_SHOWN]
    years = Counter(hit.talk.year for hit in result.hits)
    return ResultsView(
        result=result,
        filters=filters,
        hits=shown,
        total=len(kept),
        year_counts=sorted(years.items(), reverse=True),
        slide_count=sum(hit.talk.has_slides for hit in result.hits),
        video_count=sum(hit.talk.has_video for hit in result.hits),
        top_questions=[hit.questions[0] for hit in shown if hit.questions][:4],
        words=result.highlight_terms,
        stats=talk_stats(session, [hit.talk.ref for hit in shown]),
        popular_tags=services.catalog.popular_tags(),
    )


def search_response(
    request: Request, services: Services, query: str, filters: Filters | None = None
) -> HTMLResponse:
    filters = filters or Filters()
    result = services.index.search(query, limit=None) if query.strip() else None
    if result is None:
        home = {
            "result": None,
            "popular_tags": services.catalog.popular_tags(),
            "stats": services.catalog.stats(),
        }
        return services.templates.TemplateResponse(request, "home.html", home)
    with db.begin() as session:
        view = results_view(services, result, filters, session)
        context = attrs.asdict(view, recurse=False)
        if not is_fragment_request(request):
            return services.templates.TemplateResponse(request, "search.html", context)
        response = services.templates.TemplateResponse(request, "partials/results.html", context)
    speakers = list(dict.fromkeys(s.slug for hit in view.hits for s in hit.talk.speakers))
    response.headers["HX-Trigger"] = hx_trigger(SPOTLIGHT, Spotlight(speakers=speakers))
    return response


@router.get("/", response_class=HTMLResponse)
def home(request: Request, services: AppServices, q: SearchQuery = "") -> HTMLResponse:
    return search_response(request, services, q)


@router.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    services: AppServices,
    *,
    q: SearchQuery = "",
    year: FilterParam = "",
    slides: FilterParam = "",
    video: FilterParam = "",
) -> HTMLResponse:
    return search_response(request, services, q, Filters.parse(year, slides, video))


@router.get("/suggest", response_class=HTMLResponse)
def suggestions(request: Request, services: AppServices, q: SearchQuery = "") -> HTMLResponse:
    """Predictions for the search box, as list items for the listbox under it."""
    context = {"suggestions": suggest(services.catalog, q)}
    response = services.templates.TemplateResponse(request, "partials/suggest.html", context)
    response.headers["Cache-Control"] = "no-store"
    return response


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
    with db.begin() as session:
        context = {
            "talk": found,
            "questions": services.index.questions_for(found.ref),
            "related": services.catalog.related(found),
            "posts": thread(session, found.ref),
            "author_name": discussion_routes.remembered_name(request),
        }
        return services.templates.TemplateResponse(request, "talk.html", context)


@router.get("/browse", response_class=HTMLResponse)
def browse(request: Request, services: AppServices, tab: SearchQuery = "") -> HTMLResponse:
    """Every talk of one year, or every speaker, with a filter box (the list is filtered in the browser)."""
    catalog = services.catalog
    years = catalog.stats().years
    by_year = Counter(talk.year for talk in catalog.talks.values())
    selected = (
        tab
        if tab == "speakers" or (tab.isascii() and tab.isdigit() and int(tab) in years)
        else str(years[0] if years else "speakers")
    )
    talks = sorted(
        (talk for talk in catalog.talks.values() if selected.isdigit() and talk.year == int(selected)),
        key=lambda talk: (not talk.extracted, talk.display_title.lower()),
    )
    context = {
        "tabs": [(str(year), by_year[year]) for year in years] + [("speakers", len(catalog.speakers))],
        "selected": selected,
        "talks": talks,
        "speakers": sorted(catalog.speakers.values(), key=lambda speaker: speaker.name.casefold()),
    }
    return services.templates.TemplateResponse(request, "browse.html", context)


@router.get("/speakers/{slug}", response_class=HTMLResponse)
def speaker(request: Request, services: AppServices, slug: str) -> HTMLResponse:
    found = services.catalog.speakers.get(slug)
    if found is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    talks = sorted(
        services.catalog.talks_of(found), key=lambda talk: (-talk.year, talk.display_title.lower())
    )
    context = {"speaker": found, "talks": talks}
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


ERROR_PAGES = {
    404: ("Page not found", "We could not find that page. It may have moved, or the link may be wrong."),
    500: ("Something went wrong", "That was our mistake, not yours. Please try again in a moment."),
}


def wants_html(request: Request) -> bool:
    """Browsers and htmx requests get a page; API clients keep the JSON answer."""
    return "text/html" in request.headers.get("accept", "") or request.headers.get("HX-Request") == "true"


def error_page(request: Request, status_code: int) -> HTMLResponse:
    title, message = ERROR_PAGES.get(status_code, ("Something went wrong", "Please try again in a moment."))
    services = request.app.state.services
    context = {
        "status": status_code,
        "title": title,
        "message": message,
        "popular_tags": services.catalog.popular_tags(),
    }
    return services.templates.TemplateResponse(request, "error.html", context, status_code=status_code)


async def http_error(request: Request, error: Exception) -> Response:
    if not isinstance(error, StarletteHTTPException):
        raise error
    if not wants_html(request):
        return await http_exception_handler(request, error)
    return error_page(request, error.status_code)


async def server_error(request: Request, _error: Exception) -> Response:
    if not wants_html(request):
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    return error_page(request, 500)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Orgestra")
    resolved = settings or Settings.from_env()
    resolved.db_path.parent.mkdir(parents=True, exist_ok=True)
    db.initialize(f"sqlite:///{resolved.db_path}")
    db.create_all()
    app.state.services = build_services(resolved)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.include_router(router)
    app.include_router(discussion_routes.router)
    app.include_router(reports_routes.router)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(Exception, server_error)
    return app
