"""The DOM events between the server and the three.js stage, written down once.

The TypeScript side mirrors these in frontend/src/events.ts. Server to stage: an `HX-Trigger`
response header, which htmx dispatches as a DOM event on the requesting element (it bubbles to
`document`). Conversation turns arrive over SSE as `<li data-say-*>` fragments; the stage turns each
new one into a `character:say` event.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

SPOTLIGHT = "character:spotlight"
SAY = "character:say"


class Spotlight(BaseModel):
    """Characters whose talks match the current search step forward."""

    model_config = ConfigDict(frozen=True)

    speakers: list[str]


def hx_trigger(name: str, payload: BaseModel) -> str:
    """The value of an `HX-Trigger` header that fires one event with a JSON detail."""
    return f'{{"{name}": {payload.model_dump_json()}}}'
