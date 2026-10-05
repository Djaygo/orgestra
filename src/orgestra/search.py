"""Fuzzy, thesaurus-expanded search over talks and the questions extracted from them."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

import attrs
from rapidfuzz import fuzz, process

from orgestra.dataset import Catalog, Talk
from orgestra.questions import Question, extract_questions
from orgestra.slides import SlidePage
from orgestra.text import Terms, terms
from orgestra.thesaurus import Concept, Thesaurus

FIELD_WEIGHTS = {"title": 3.0, "tags": 2.0, "speakers": 2.0, "questions": 1.5, "abstract": 1.0}
SYNONYM_WEIGHT = 0.7
# Talks only known by their schedule slug rank below talks with an abstract and speakers.
UNEXTRACTED_WEIGHT = 0.5
TYPO_MIN_LENGTH = 4
TYPO_MIN_SIMILARITY = 80
MAX_QUESTIONS_PER_HIT = 3
# A deck adds at most SLIDES_WEIGHT * MAX_SLIDE_PAGES to a talk's score, however many words the query has: below
# a title match even of a talk without details (3.0 * UNEXTRACTED_WEIGHT).
SLIDES_WEIGHT = 0.4
MAX_SLIDE_PAGES = 3
SLIDES_CAP = SLIDES_WEIGHT * MAX_SLIDE_PAGES
FIELD_LABELS = {
    "title": "Title",
    "tags": "Tag",
    "speakers": "Speaker",
    "questions": "Question",
    "abstract": "Abstract",
    "slides": "Slides",
}
# Equal scores list the more telling field first.
FIELD_ORDER = tuple(FIELD_LABELS)


@attrs.frozen
class PageTerms:
    number: int
    terms: Terms


@attrs.frozen
class Document:
    talk: Talk
    fields: dict[str, Terms]
    questions: list[Question]
    question_terms: list[Terms]
    pages: list[PageTerms]


@attrs.frozen
class FieldMatch:
    """How much one field contributed to a hit, summed over the query's concepts."""

    field: str
    score: float

    @property
    def label(self) -> str:
        return FIELD_LABELS[self.field]


@attrs.frozen
class Hit:
    talk: Talk
    score: float
    questions: list[Question]
    matches: list[FieldMatch]
    slide_page: int | None


@attrs.frozen
class SearchResult:
    query: str
    concepts: list[Concept]
    hits: list[Hit]

    def top_questions(self, limit: int = 4) -> list[Question]:
        """The best-ranked talks' first matching questions, for a "People also ask" box."""
        return [hit.questions[0] for hit in self.hits if hit.questions][:limit]


def occurrences(variant: Terms, field: Terms) -> int:
    """How often the variant appears in the field as a contiguous run of terms."""
    size = len(variant)
    return sum(1 for start in range(len(field) - size + 1) if field[start : start + size] == variant)


def document_for(talk: Talk, slides: Iterable[SlidePage] = ()) -> Document:
    questions = extract_questions(talk)
    fields = {
        "title": terms(talk.display_title),
        "tags": tuple(t for tag in talk.tags for t in terms(tag)),
        "speakers": tuple(t for speaker in talk.speakers for t in terms(speaker.name)),
        "questions": tuple(t for question in questions for t in terms(question.text)),
        "abstract": terms(talk.abstract or ""),
    }
    pages = [PageTerms(page.number, terms(page.text)) for page in slides]
    return Document(talk, fields, questions, [terms(question.text) for question in questions], pages)


@attrs.frozen
class SearchIndex:
    documents: list[Document]
    vocabulary: frozenset[str]
    thesaurus: Thesaurus

    @classmethod
    def build(
        cls, catalog: Catalog, thesaurus: Thesaurus, slides: dict[str, list[SlidePage]] | None = None
    ) -> SearchIndex:
        slides = slides or {}
        documents = [document_for(talk, slides.get(talk.ref, [])) for talk in catalog.talks.values()]
        vocabulary = frozenset(
            t for doc in documents for field in doc.fields.values() for t in field
        ) | frozenset(t for doc in documents for page in doc.pages for t in page.terms)
        return cls(documents=documents, vocabulary=vocabulary, thesaurus=thesaurus)

    def search(self, query: str, limit: int = 20) -> SearchResult:
        concepts = [self._with_typo_fixes(concept) for concept in self.thesaurus.expand(query)]
        if not concepts:
            return SearchResult(query=query, concepts=[], hits=[])
        hits = [hit for doc in self.documents if (hit := score_document(doc, concepts)) is not None]
        hits.sort(key=lambda hit: (-hit.score, hit.talk.display_title))
        return SearchResult(query=query, concepts=concepts, hits=hits[:limit])

    def _with_typo_fixes(self, concept: Concept) -> Concept:
        """Add the closest indexed words for typed words the index has never seen."""
        typed = terms(concept.label)
        fixed = tuple(self._closest(term) for term in typed)
        if fixed == typed:
            return concept
        return Concept(label=concept.label, variants=concept.variants | self.thesaurus.synonyms(fixed))

    def _closest(self, term: str) -> str:
        if term in self.vocabulary or len(term) < TYPO_MIN_LENGTH:
            return term
        match = process.extractOne(term, self.vocabulary, scorer=fuzz.ratio, score_cutoff=TYPO_MIN_SIMILARITY)
        return match[0] if match else term

    def questions_for(self, talk_ref: str) -> list[Question]:
        return next((doc.questions for doc in self.documents if doc.talk.ref == talk_ref), [])


def score_document(doc: Document, concepts: list[Concept]) -> Hit | None:
    """Sum of concept scores, scaled down by the share of concepts the talk does not match."""
    breakdowns = cap_slides([concept_breakdown(doc, concept) for concept in concepts])
    scores = [sum(breakdown.values()) for breakdown in breakdowns]
    matched = sum(1 for score in scores if score > 0)
    if not matched:
        return None
    coverage = matched / len(concepts)
    weight = 1.0 if doc.talk.extracted else UNEXTRACTED_WEIGHT
    return Hit(
        talk=doc.talk,
        score=sum(scores) * coverage * coverage * weight,
        questions=matching_questions(doc, concepts),
        matches=field_matches(breakdowns),
        slide_page=best_slide_page(doc, concepts),
    )


def variant_scores(doc: Document, variant: Terms) -> dict[str, float]:
    scores = {name: weight * occurrences(variant, doc.fields[name]) for name, weight in FIELD_WEIGHTS.items()}
    pages = sum(1 for page in doc.pages if occurrences(variant, page.terms))
    scores["slides"] = SLIDES_WEIGHT * min(pages, MAX_SLIDE_PAGES)
    return scores


def concept_breakdown(doc: Document, concept: Concept) -> dict[str, float]:
    """Per-field scores of the concept's best-scoring variant (a synonym counts less than the typed word)."""
    typed = terms(concept.label)
    best: dict[str, float] = {}
    for variant in sorted(concept.variants):  # a fixed order, so ties give the same badges on every start
        factor = 1.0 if variant == typed else SYNONYM_WEIGHT
        scores = {name: factor * score for name, score in variant_scores(doc, variant).items()}
        if sum(scores.values()) > sum(best.values()):
            best = scores
    return best


def cap_slides(breakdowns: list[dict[str, float]]) -> list[dict[str, float]]:
    """Scale the slide scores down so the deck adds at most SLIDES_CAP over all the query's words."""
    total = sum(breakdown.get("slides", 0.0) for breakdown in breakdowns)
    if total <= SLIDES_CAP:
        return breakdowns
    factor = SLIDES_CAP / total
    return [{**breakdown, "slides": breakdown.get("slides", 0.0) * factor} for breakdown in breakdowns]


def field_matches(breakdowns: list[dict[str, float]]) -> list[FieldMatch]:
    totals: Counter[str] = Counter()
    for breakdown in breakdowns:
        totals.update(breakdown)
    ranked = sorted(totals.items(), key=lambda item: (-item[1], FIELD_ORDER.index(item[0])))
    return [FieldMatch(field, score) for field, score in ranked if score > 0]


def best_slide_page(doc: Document, concepts: list[Concept]) -> int | None:
    """The page matching the most concepts, then the most words, then the lowest number."""
    best: tuple[tuple[int, int, int], int] | None = None
    for page in doc.pages:
        counts = [
            sum(occurrences(variant, page.terms) for variant in concept.variants) for concept in concepts
        ]
        matched = sum(1 for count in counts if count)
        if not matched:
            continue
        rank = (matched, sum(counts), -page.number)
        if best is None or rank > best[0]:
            best = (rank, page.number)
    return best[1] if best else None


def matches_any(question_terms: Terms, variants: Iterable[Terms]) -> bool:
    return any(occurrences(variant, question_terms) for variant in variants)


def matching_questions(doc: Document, concepts: list[Concept]) -> list[Question]:
    variants = [variant for concept in concepts for variant in concept.variants]
    found = [q for q, qt in zip(doc.questions, doc.question_terms, strict=True) if matches_any(qt, variants)]
    return (found or doc.questions)[:MAX_QUESTIONS_PER_HIT]
