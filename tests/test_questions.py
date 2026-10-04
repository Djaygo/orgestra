from orgestra.questions import QuestionSource, extract_questions, summary

from .conftest import make_talk


def test_questions_in_the_abstract_are_answered_by_what_follows():
    talk = make_talk("t", abstract="Why do clusters fall over? Because nobody owns them.")
    [question, *_] = extract_questions(talk)
    assert question.text == "Why do clusters fall over?"
    assert question.answer == "Because nobody owns them."
    assert question.source is QuestionSource.ABSTRACT


def test_generated_questions_name_title_speakers_and_tags():
    talk = make_talk(
        "t",
        title="Kubernetes at Scale",
        tags=["platforms", "Keynote"],
        format="Keynote",
        speakers=[{"slug": "a", "name": "Ada"}, {"slug": "b", "name": "Bob"}, {"slug": "c", "name": "Cy"}],
    )
    texts = [q.text for q in extract_questions(talk)]
    assert "Who presented “Kubernetes at Scale”?" in texts
    assert "What does Ada, Bob and Cy say about platforms?" in texts
    assert not any("Keynote" in text for text in texts)


def test_talks_without_details_have_no_questions():
    assert extract_questions(make_talk("t", extracted=False, title=None)) == []


def test_summary_stops_at_the_length_limit():
    assert summary("One. " + "Two " * 100 + ".") == "One."
