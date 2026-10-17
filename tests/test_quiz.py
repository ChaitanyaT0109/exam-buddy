"""Quiz logic with a fake Sarvam client: no network, no credits."""

import json
from pathlib import Path

import pytest

from exam_buddy.grader import CORRECT, INCORRECT, PARTIAL, SKIPPED, grade_answer, is_skip
from exam_buddy.jsonutil import ModelReplyError, extract_json
from exam_buddy.notes import NotesError, load_notes
from exam_buddy.quiz import Question, generate_questions, parse_questions
from exam_buddy.session import QuizSession

SAMPLE = Path(__file__).resolve().parents[1] / "notes" / "sample-dbms-normalization.md"
QUESTIONS = [
    {"question": "What does 1NF require?", "answer": "Atomic values in every column.",
     "explanation": "One value per cell.", "topic": "1NF", "difficulty": "easy"},
    {"question": "What does 2NF remove?", "answer": "Partial dependencies.",
     "explanation": "Depend on the whole key.", "topic": "2NF", "difficulty": "medium"},
    {"question": "When is a table in BCNF?", "answer": "Every determinant is a superkey.",
     "explanation": "Stricter than 3NF.", "topic": "BCNF", "difficulty": "hard"},
]


class FakeClient:
    """Returns queued replies in order and records the prompts it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def chat(self, messages, temperature=0.3, max_tokens=None, json_mode=False):
        self.prompts.append(messages[-1]["content"])
        return self.replies.pop(0)


def test_extract_json_handles_fences_and_reasoning():
    reply = "<think>let me plan</think>\nHere you go:\n```json\n[{\"a\": 1}]\n```"
    assert extract_json(reply) == [{"a": 1}]
    assert extract_json('Sure! {"verdict": "correct"}') == {"verdict": "correct"}
    with pytest.raises(ModelReplyError):
        extract_json("no json here")


def test_parse_questions_cleans_and_numbers():
    reply = json.dumps({"questions": QUESTIONS + [{"question": "", "answer": "x"}, "junk"]})
    questions = parse_questions(reply, n=5)
    assert [q.id for q in questions] == [1, 2, 3]
    assert questions[1].topic == "2NF" and questions[2].difficulty == "hard"


def test_generate_questions_retries_once_on_bad_json():
    client = FakeClient("sorry, here are some questions", json.dumps(QUESTIONS))
    questions = generate_questions(client, "notes " * 20, n=2, language="hi-IN")
    assert len(questions) == 2
    assert "Hindi" in client.prompts[0]


def test_generate_questions_rejects_unknown_language():
    with pytest.raises(ValueError):
        generate_questions(FakeClient(), "notes", language="xx-XX")


@pytest.mark.parametrize("answer", ["I don't know", "skip", "pass", "no idea", "pata nahi", "मुझे नहीं पता", "  "])
def test_skip_answers_never_call_the_model(answer):
    question = Question(1, "Q?", "A.", "E.", "T", "easy")
    grade = grade_answer(FakeClient(), question, answer)  # an empty FakeClient would fail if it were called
    assert grade.verdict == SKIPPED and grade.points == 0 and grade.correct_answer == "A."


def test_grade_uses_model_verdict_and_falls_back_safely():
    question = Question(1, "What does 2NF remove?", "Partial dependencies.", "Whole key.", "2NF", "medium")
    good = FakeClient('{"verdict": "correct", "feedback": "Spot on."}')
    assert grade_answer(good, question, "partial dependency").verdict == CORRECT
    bad = FakeClient("I think it is fine")
    fallback = grade_answer(bad, question, "something")
    assert fallback.verdict == PARTIAL and "compare" in fallback.feedback
    weird = FakeClient('{"verdict": "excellent"}')
    assert grade_answer(weird, question, "x").verdict == PARTIAL


def test_session_scores_and_lists_topics_to_revise():
    client = FakeClient(json.dumps(QUESTIONS),
                        '{"verdict": "correct", "feedback": "Yes."}',
                        '{"verdict": "incorrect", "feedback": "Not quite."}')
    session = QuizSession.from_notes(client, "notes " * 20, n=3)
    assert session.current.id == 1
    assert session.submit(client, "atomic values").verdict == CORRECT
    assert session.submit(client, "transitive dependency").verdict == INCORRECT
    assert session.submit(client, "I don't know").verdict == SKIPPED
    assert session.done and session.current is None
    summary = session.summary()
    assert summary["score"] == 1 and summary["total"] == 3 and summary["skipped"] == 1
    assert summary["topics_to_revise"] == ["2NF", "BCNF"]
    with pytest.raises(ValueError):
        session.submit(client, "too late")


def test_load_notes_reads_markdown_and_rejects_bad_input():
    text = load_notes(SAMPLE.read_bytes(), SAMPLE.name)
    assert "Boyce-Codd" in text and len(text) <= 15_000
    with pytest.raises(NotesError):
        load_notes(b"tiny", "notes.txt")
    with pytest.raises(NotesError):
        load_notes(b"x" * 100, "notes.exe")
    with pytest.raises(NotesError):
        load_notes(b"x" * 100, "photo.jpg")  # photos need a Sarvam client
