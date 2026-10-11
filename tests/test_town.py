import json

import pytest
from fastapi.testclient import TestClient

from orgestra.app import REPO_DATA_DIR, Settings, create_app
from orgestra.town.expo import Expo, load_expo
from orgestra.town.rooms import rooms
from tests.conftest import make_talk


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "orgestra.db"
    return TestClient(create_app(Settings(data_dir=REPO_DATA_DIR, db_path=db_path)))


def test_every_sponsor_sells_seeds_and_a_stand_costs_less_than_its_seeds():
    expo = load_expo()

    for sponsor in expo.sponsors:
        seeds = expo.seeds_of(sponsor)
        assert seeds
        assert expo.bundle_price(sponsor) < sum(seed.price for seed in seeds)
    assert sum(seed.price for seed in expo.seeds) > expo.budget  # the budget makes you choose


def test_a_seed_without_a_sponsor_is_rejected():
    seed = load_expo().seeds[0].model_dump() | {"sponsor": "nobody"}

    with pytest.raises(ValueError, match="without a sponsor"):
        Expo.model_validate({"budget": 10, "sponsors": [], "seeds": [seed]})


def test_rooms_are_the_busiest_of_the_newest_year_without_the_venue_prefix(catalog):
    talks = {
        **catalog.talks,
        "2026/a": make_talk("a", year=2026, room="TAP1, Main Stage", start="10:00"),
        "2026/b": make_talk("b", year=2026, room="TAP1, Main Stage", start="09:00"),
        "2026/c": make_talk("c", year=2026, room="Room 2"),
        "2025/old": make_talk("old", room="Old Hall"),
    }
    found = rooms(type(catalog)(organizations=catalog.organizations, talks=talks, speakers=catalog.speakers))

    assert [room.name for room in found] == ["Main Stage", "Room 2"]
    assert [talk.slug for talk in found[0].talks] == ["b", "a"]


def test_town_page_embeds_booths_rooms_and_cast_without_the_plaza(client):
    html = client.get("/town").text
    town = json.loads(html.split('id="town-data">')[1].split("</script>")[0])

    assert town["booths"][0]["slug"] == "pipeline-pals"
    assert all(booth["seeds"] and booth["bundle"] for booth in town["booths"])
    assert len(town["rooms"]) == 3
    assert all(room["showing"] for room in town["rooms"])
    assert 'id="cast-data"' in html
    assert 'id="stage"' not in html
    assert 'hx-boost="false"' in html


def test_booth_panel_sells_its_seeds_and_the_stand(client):
    html = client.get("/town/booths/pipeline-pals").text

    assert "<html" not in html
    assert 'data-add-seed="ci-check-watch"' in html
    assert 'data-add-stand="pipeline-pals"' in html
    assert "<code>pr-checks</code>" in html


def test_room_panel_lists_its_talks(client):
    html = client.get("/town/rooms/1").text

    assert "Main Stage" in html
    assert 'href="/talks/' in html


@pytest.mark.parametrize("path", ["/town/booths/nobody", "/town/rooms/0", "/town/rooms/4"])
def test_unknown_booths_and_rooms_are_not_found(client, path):
    assert client.get(path).status_code == 404
