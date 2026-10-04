"""The bug report form: filed as an issue on the forge, or a plain error page when that fails."""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, BeforeValidator, StringConstraints

from orgestra.discussion.models import utc_now
from orgestra.reports.body import issue_body, issue_title
from orgestra.reports.tracker import IssueTracker, TrackerError

logger = logging.getLogger(__name__)
MAX_PAGE_CHARS = 500
# One slash, then no second slash or backslash and no control character or space: browsers strip tabs and
# line breaks from a URL, so "/<tab>/host" would otherwise become "//host".
LOCAL_PATH = re.compile(r"/(?![/\\])[^\x00-\x20\x7f]*")


def unix_newlines(value: object) -> object:
    """A browser submits each line break as CRLF although the form's maxlength counted one character."""
    return value.replace("\r\n", "\n") if isinstance(value, str) else value


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5000),
    BeforeValidator(unix_newlines),
]


class Report(BaseModel):
    title: Title
    description: Description
    page: str = ""


router = APIRouter()


def safe_page(value: str) -> str:
    """A path on this site, or empty: external, protocol-relative and backslash forms are dropped."""
    return value if LOCAL_PATH.fullmatch(value) and len(value) <= MAX_PAGE_CHARS else ""


def require_tracker(request: Request) -> IssueTracker:
    tracker = request.app.state.services.tracker
    if tracker is None:
        raise HTTPException(status_code=404, detail="Not found")
    return tracker


Tracker = Annotated[IssueTracker, Depends(require_tracker)]


def render(request: Request, name: str, context: dict[str, Any], status_code: int = 200) -> HTMLResponse:
    templates = request.app.state.services.templates
    return templates.TemplateResponse(request, name, context, status_code=status_code)


@router.get("/report", response_class=HTMLResponse)
def report_form(
    request: Request, _: Tracker, origin: Annotated[str, Query(alias="from", max_length=2000)] = ""
) -> HTMLResponse:
    return render(request, "report.html", {"page": safe_page(origin)})


@router.post("/report", response_class=HTMLResponse)
def send_report(request: Request, tracker: Tracker, form: Annotated[Report, Form()]) -> HTMLResponse:
    page = safe_page(form.page)
    body = issue_body(form.description, page, request.headers.get("user-agent", ""), utc_now())
    try:
        issue = tracker.create_issue(issue_title(form.title), body)
    except TrackerError as error:
        logger.error("could not file a bug report: %s", error)
        return render(request, "report_failed.html", {"page": page}, status_code=502)
    return render(request, "report_sent.html", {"number": issue.number, "page": page})
