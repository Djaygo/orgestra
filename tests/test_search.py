from typing import cast

import pytest

from orgestra.search import (
    MAX_SLIDE_PAGES,
    SLIDES_WEIGHT,
    Document,
    SearchIndex,
    concept_breakdown,
    occurrences,
)
from orgestra.slides import SlidePage
from orgestra.text import Terms
from orgestra.thesaurus import Concept
from tests.conftest import make_talk


@pytest.fixture
def index(catalog, thesaurus):
    return SearchIndex.build(catalog, thesaurus)


def titles(result):
    return [hit.talk.display_title for hit in result.hits]


def test_exact_word(index):
    assert titles(index.search("kubernetes"))[0] == "Kubernetes at Scale"


def test_talks_without_details_rank_below_talks_with_details(index):
    assert titles(index.search("kubernetes")) == ["Kubernetes at Scale", "Kubernetes unplugged"]


def test_synonym_finds_talks_that_never_use_the_word(index):
    assert titles(index.search("llm")) == ["Large Language Models in Production"]


def test_typo_is_corrected_to_an_indexed_word(index):
    assert titles(index.search("kubernets"))[0] == "Kubernetes at Scale"


def test_talks_matching_every_concept_rank_first(index):
    assert titles(index.search("platforms chatbot"))[0] == "Large Language Models in Production"


def test_matching_questions_are_returned_with_the_hit(index):
    [hit] = index.search("clusters").hits
    assert hit.questions[0].text == "Why do clusters fall over?"


def test_speaker_names_are_searchable(index):
    assert titles(index.search("hopper")) == ["Large Language Models in Production"]


def test_empty_query(index):
    assert index.search("  ").hits == []


def test_occurrences_counts_contiguous_runs():
    assert occurrences(("a", "b"), ("a", "b", "c", "a", "b")) == 2
    assert occurrences(("a", "c"), ("a", "b", "c")) == 0


def test_a_word_only_in_a_deck_finds_the_talk_and_the_page(catalog, thesaurus):
    slides = {
        "2025/llms-in-production": [SlidePage(1, "Welcome"), SlidePage(7, "Quokka routing in practice")]
    }

    hits = SearchIndex.build(catalog, thesaurus, slides).search("quokka").hits

    assert [hit.talk.slug for hit in hits] == ["llms-in-production"]
    assert hits[0].slide_page == 7
    assert [(m.field, m.label) for m in hits[0].matches] == [("slides", "Slides")]


def test_the_best_page_matches_the_most_concepts_then_the_most_words(catalog, thesaurus):
    slides = {
        "2025/llms-in-production": [
            SlidePage(2, "quokka"),
            SlidePage(5, "quokka wombat"),
            SlidePage(6, "quokka quokka wombat"),
        ]
    }

    hit = SearchIndex.build(catalog, thesaurus, slides).search("quokka wombat").hits[0]

    assert hit.slide_page == 6


def test_slide_repetition_is_capped_and_cannot_beat_a_title(catalog, thesaurus):
    many = [SlidePage(number, "kubernetes") for number in range(1, 40)]
    index = SearchIndex.build(catalog, thesaurus, {"2025/llms-in-production": many})

    hits = index.search("kubernetes").hits

    assert hits[0].talk.slug == "kubernetes-at-scale"
    deck_hit = next(hit for hit in hits if hit.talk.slug == "llms-in-production")
    assert deck_hit.matches[0].score == pytest.approx(SLIDES_WEIGHT * MAX_SLIDE_PAGES)


def test_matches_name_the_contributing_fields_best_first(index):
    hit = index.search("kubernetes").hits[0]

    fields = [match.field for match in hit.matches]
    assert fields[0] == "title"
    assert set(fields) <= {"title", "tags", "speakers", "questions", "abstract"}
    assert hit.matches[0].label == "Title"
    assert all(match.score > 0 for match in hit.matches)
    assert hit.slide_page is None


def test_without_slides_the_results_are_unchanged(catalog, thesaurus):
    plain = SearchIndex.build(catalog, thesaurus)
    empty = SearchIndex.build(catalog, thesaurus, {})

    for query in ("kubernetes", "chatbot", "platforms"):
        assert [(h.talk.ref, h.score) for h in plain.search(query).hits] == [
            (h.talk.ref, h.score) for h in empty.search(query).hits
        ]


def test_slides_add_at_most_one_cap_to_a_talk_however_many_words_the_query_has(catalog, thesaurus):
    pages = [SlidePage(number, "quokka wombat") for number in range(1, 20)]
    index = SearchIndex.build(catalog, thesaurus, {"2025/llms-in-production": pages})

    hit = index.search("quokka wombat").hits[0]

    slides = next(match for match in hit.matches if match.field == "slides")
    assert slides.score == pytest.approx(SLIDES_WEIGHT * MAX_SLIDE_PAGES)


def test_a_deck_alone_ranks_below_a_title_match_of_a_talk_without_details(catalog, thesaurus):
    many = [SlidePage(number, "kubernetes") for number in range(1, 40)]
    index = SearchIndex.build(catalog, thesaurus, {"2025/llms-in-production": many})

    scores = {hit.talk.slug: hit.score for hit in index.search("kubernetes").hits}

    assert scores["kubernetes-unplugged"] > scores["llms-in-production"]


def ordered(*variants: Terms) -> frozenset[Terms]:
    """A stand-in whose iteration order is the order given: the order a set would pick by chance."""
    return cast("frozenset[Terms]", list(variants))


def test_badges_do_not_depend_on_the_order_synonyms_are_tried_in():
    fields: dict[str, Terms] = {
        "title": ("a",),
        "tags": ("b",),
        "speakers": (),
        "questions": (),
        "abstract": ("b",),
    }
    doc = Document(make_talk("tie"), fields, [], [], [])

    forward = concept_breakdown(doc, Concept(label="zzz", variants=ordered(("a",), ("b",))))
    backward = concept_breakdown(doc, Concept(label="zzz", variants=ordered(("b",), ("a",))))

    assert forward == backward
