"""Form endpoints for the discussion. Every mutation answers 303 back to the talk page."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from orgestra.discussion import store
from orgestra.discussion.models import Kind, Post, db

NAME_COOKIE = "orgestra_name"
YEAR = 365 * 24 * 3600

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class NewPost(BaseModel):
    kind: Kind
    name: Name
    body: Body


class Reply(BaseModel):
    name: Name
    body: Body


class Restore(BaseModel):
    name: Name


router = APIRouter()


def remembered_name(request: Request) -> str:
    """The display name the visitor last used; percent-encoded so non-ASCII names survive."""
    return unquote(request.cookies.get(NAME_COOKIE, ""))


def see_post(post: Post, name: str) -> RedirectResponse:
    response = RedirectResponse(f"/talks/{post.talk_ref}#post-{post.id}", status_code=303)
    if name:
        response.set_cookie(NAME_COOKIE, quote(name), max_age=YEAR, samesite="lax")
    return response


def find_post(session: Session, post_id: int) -> Post:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/talks/{year}/{slug}/posts")
def new_post(request: Request, year: int, slug: str, form: Annotated[NewPost, Form()]) -> RedirectResponse:
    ref = f"{year}/{slug}"
    if ref not in request.app.state.services.catalog.talks:
        raise HTTPException(status_code=404, detail="Talk not found")
    with db.begin() as session:
        post = store.add_post(session, ref, form.kind, form.name, form.body)
        return see_post(post, form.name)


@router.post("/posts/{post_id}/replies")
def reply(post_id: int, form: Annotated[Reply, Form()]) -> RedirectResponse:
    with db.begin() as session:
        created = store.add_reply(session, find_post(session, post_id), form.name, form.body)
        return see_post(created, form.name)


@router.post("/posts/{post_id}/edit")
def edit(post_id: int, form: Annotated[Reply, Form()]) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        store.edit_post(session, post, form.name, form.body)
        return see_post(post, form.name)


@router.post("/posts/{post_id}/restore/{revision_id}")
def restore(post_id: int, revision_id: int, form: Annotated[Restore, Form()]) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        try:
            store.restore_revision(session, post, revision_id, form.name)
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Revision not found") from error
        return see_post(post, form.name)


@router.post("/posts/{post_id}/answered")
def answered(request: Request, post_id: int) -> RedirectResponse:
    with db.begin() as session:
        post = find_post(session, post_id)
        try:
            store.toggle_answered(post)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return see_post(post, remembered_name(request))
