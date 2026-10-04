import pytest

from orgestra.search import SearchIndex, occurrences


@pytest.fixture
def index(catalog, thesaurus):
    return SearchIndex.build(catalog, thesaurus)


def titles(result):
    return [hit.talk.display_title for hit in result.hits]


def test_exact_word(index):
    assert titles(index.search("kubernetes")) == ["Kubernetes at Scale"]


def test_synonym_finds_talks_that_never_use_the_word(index):
    assert titles(index.search("llm")) == ["Large Language Models in Production"]


def test_typo_is_corrected_to_an_indexed_word(index):
    assert titles(index.search("kubernets")) == ["Kubernetes at Scale"]


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
