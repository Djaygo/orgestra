from orgestra.personas import initials, persona_hue


def test_hue_matches_the_frontend_hash():
    # Same values as frontend/src/persona.test.ts
    assert persona_hue("martin-fowler") == 70
    assert persona_hue("sarah-meiklejohn") == 287


def test_initials():
    assert initials("Ada Lovelace") == "AL"
    assert initials("Cher") == "CH"
