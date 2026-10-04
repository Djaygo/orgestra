"""Extract the questions a talk answers, so search can match what people ask.

Today the sources are the talk's metadata and abstract; slide text joins them once the decks are
downloaded. Each question keeps a pointer back to the talk it came from.
"""

from __future__ import annotations

import re
from enum import StrEnum

import attrs

from orgestra.dataset import Talk

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_ANSWER_CHARS = 280


class QuestionSource(StrEnum):
    ABSTRACT = "abstract"
    GENERATED = "generated"


@attrs.frozen
class Question:
    text: str
    answer: str
    talk_ref: str
    source: QuestionSource


def sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_END.split(text) if part.strip()]


def summary(text: str) -> str:
    """The first sentences of a text, up to MAX_ANSWER_CHARS."""
    result = ""
    for sentence in sentences(text):
        if result and len(result) + len(sentence) > MAX_ANSWER_CHARS:
            break
        result = f"{result} {sentence}".strip()
    return result


def speaker_names(talk: Talk) -> str:
    names = [speaker.name for speaker in talk.speakers]
    return f"{', '.join(names[:-1])} and {names[-1]}" if len(names) > 1 else "".join(names)


def abstract_questions(talk: Talk) -> list[Question]:
    """Questions the speaker asks in the abstract; the sentences after each one answer it."""
    parts = sentences(talk.abstract or "")
    return [
        Question(
            text=part,
            answer=summary(" ".join(parts[index + 1 :])) or summary(talk.abstract or ""),
            talk_ref=talk.ref,
            source=QuestionSource.ABSTRACT,
        )
        for index, part in enumerate(parts)
        if part.endswith("?")
    ]


def generated_questions(talk: Talk) -> list[Question]:
    if not talk.extracted or not talk.title:
        return []
    about = summary(talk.abstract or "") or talk.title
    names = speaker_names(talk)
    questions = [Question(f"What is “{talk.title}” about?", about, talk.ref, QuestionSource.GENERATED)]
    if names:
        questions.append(
            Question(f"Who presented “{talk.title}”?", names, talk.ref, QuestionSource.GENERATED)
        )
        questions.extend(
            Question(f"What does {names} say about {tag}?", about, talk.ref, QuestionSource.GENERATED)
            for tag in talk.tags
            if tag.lower() not in {fmt.lower() for fmt in talk.formats}
        )
    return questions


def extract_questions(talk: Talk) -> list[Question]:
    return abstract_questions(talk) + generated_questions(talk)
