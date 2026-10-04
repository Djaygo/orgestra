import random

from orgestra.app import transcript_frames
from orgestra.conversations import conversation, conversations, personas


def test_personas_are_speakers_with_a_known_talk(catalog):
    assert [p.speaker.slug for p in personas(catalog)] == ["ada", "grace"]


def test_a_conversation_alternates_and_mentions_a_shared_tag(catalog):
    ada, grace = personas(catalog)
    turns = conversation(ada, grace)
    assert [t.speaker_slug for t in turns] == ["ada", "grace"] * 3
    assert "platforms" in turns[3].text
    assert turns[2].text == "Why do clusters fall over?"


def test_conversations_need_two_people(catalog):
    assert list(conversations(personas(catalog)[:1], random.Random(1))) == []


def test_transcript_frames_grow_then_restart(catalog):
    script = conversations(personas(catalog), random.Random(1))
    frames = [len(frame) for _, frame in zip(range(8), transcript_frames(script), strict=False)]
    assert frames == [1, 2, 3, 4, 5, 6, 1, 2]
