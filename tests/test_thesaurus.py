from orgestra.text import terms
from orgestra.thesaurus import Thesaurus


def test_expands_a_word_to_its_synonyms(thesaurus):
    [concept] = thesaurus.expand("LLM")
    assert terms("large language model") in concept.variants
    assert "large language model" in concept.alternatives


def test_prefers_the_longest_known_phrase(thesaurus):
    concepts = thesaurus.expand("machine learning pipelines")
    assert [c.label for c in concepts] == ["machine learning", "pipelines"]
    assert terms("ml") in concepts[0].variants


def test_unknown_words_are_their_own_concept():
    thesaurus = Thesaurus.from_groups([["k8s", "kubernetes"]])
    [concept] = thesaurus.expand("jazz")
    assert concept.variants == {("jazz",)}
    assert concept.alternatives == []
