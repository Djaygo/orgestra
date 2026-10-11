"""The /town page and the panels its booths and rooms open (htmx fragments)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from orgestra.town.expo import Expo
from orgestra.town.rooms import Room, rooms

router = APIRouter()
# What the island needs of a seed to show and price it; the booth panel renders the rest.
SEED_FIELDS = {"slug", "name", "price", "hook", "product"}


def town_json(expo: Expo, room_list: list[Room]) -> str:
    """What the town island draws and prices, embedded in the page as JSON."""
    payload = {
        "budget": expo.budget,
        "booths": [
            {
                "slug": sponsor.slug,
                "name": sponsor.name,
                "color": sponsor.color,
                "bundle": expo.bundle_price(sponsor),
                "seeds": [seed.model_dump(include=SEED_FIELDS) for seed in expo.seeds_of(sponsor)],
            }
            for sponsor in expo.sponsors
        ],
        "rooms": [{"name": room.name, "showing": room.showing} for room in room_list],
    }
    # Safe inside <script type="application/json">: no "</script>" can appear.
    return json.dumps(payload).replace("<", "\\u003c")


@router.get("/town", response_class=HTMLResponse)
def town(request: Request) -> HTMLResponse:
    services = request.app.state.services
    room_list = rooms(services.catalog)
    context = {"town_json": town_json(services.expo, room_list), "expo": services.expo, "rooms": room_list}
    return services.templates.TemplateResponse(request, "town.html", context)


@router.get("/town/booths/{slug}", response_class=HTMLResponse)
def booth(request: Request, slug: str) -> HTMLResponse:
    services = request.app.state.services
    expo: Expo = services.expo
    sponsor = expo.sponsor(slug)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Booth not found")
    context = {"sponsor": sponsor, "seeds": expo.seeds_of(sponsor), "bundle": expo.bundle_price(sponsor)}
    return services.templates.TemplateResponse(request, "partials/town/booth.html", context)


@router.get("/town/rooms/{number}", response_class=HTMLResponse)
def room(request: Request, number: int) -> HTMLResponse:
    services = request.app.state.services
    room_list = rooms(services.catalog)
    if not 1 <= number <= len(room_list):
        raise HTTPException(status_code=404, detail="Room not found")
    context = {"room": room_list[number - 1]}
    return services.templates.TemplateResponse(request, "partials/town/room.html", context)
