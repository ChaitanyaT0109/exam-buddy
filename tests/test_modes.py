"""Learning mode and exam mode, through the library and through the web API (fake Sarvam client)."""

import json

import pytest
from fastapi.testclient import TestClient

from exam_buddy import server
from exam_buddy.grader import CORRECT, SKIPPED
from exam_buddy.session import EXAM, LEARN, QuizSession
from test_quiz import QUESTIONS, FakeClient


class FakeVoiceClient(FakeClient):
    def speak(self, text, language="en-IN"):
        return b"RIFF-fake-wav"

    def transcribe(self, audio, filename="answer.webm", language="unknown"):
        return "partial dependency"

    def chat(self, messages, temperature=0.3, max_tokens=None, json_mode=False):
        prompt = messages[-1]["content"]
        if "making a short spoken quiz" in prompt:
            return json.dumps({"questions": QUESTIONS})
        return '{"verdict": "correct", "feedback": "Well done."}'


def test_hint_caps_the_question_at_half_a_mark():
    client = FakeVoiceClient()
    session = QuizSession.from_notes(client, "notes " * 20, n=2, mode=LEARN)
    assert session.hint() == "Hint: One value per cell."
    assert session.submit(client, "atomic values").verdict == CORRECT
    assert session.attempts[0].points == 0.5          # correct, but a hint was used
    session.submit(client, "partial dependencies")
    summary = session.summary()
    assert summary["score"] == 1.5 and summary["hints_used"] == 1 and summary["percent"] == 75


def test_exam_mode_has_no_hints_and_a_time_limit():
    session = QuizSession.from_notes(FakeVoiceClient(), "notes " * 20, n=3, mode=EXAM)
    with pytest.raises(PermissionError):
        session.hint()
    assert session.time_limit == 180
    with pytest.raises(ValueError):
        QuizSession(questions=[], mode="party")


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(server, "_client", FakeVoiceClient())
    server.SESSIONS.clear()
    return TestClient(server.app)


def test_learning_mode_gives_feedback_after_each_answer(api):
    start = api.post("/api/quiz", data={"use_sample": "true", "count": "2", "mode": "learn"}).json()
    assert start["question"]["number"] == 1 and start["question"]["audio"]
    reply = api.post("/api/answer", data={"session_id": start["session_id"], "text": "atomic values"}).json()
    assert reply["grade"]["verdict"] == CORRECT and reply["feedback_audio"]
    assert reply["next_question"]["number"] == 2 and reply["summary"] is None


def test_exam_mode_hides_marks_until_the_review(api):
    start = api.post("/api/quiz", data={"use_sample": "true", "count": "3", "mode": "exam"}).json()
    sid = start["session_id"]
    assert start["seconds_per_question"] == 60
    assert api.post("/api/hint", data={"session_id": sid}).status_code == 403
    files = {"audio": ("answer.webm", b"x" * 2000, "audio/webm")}
    reply = api.post("/api/answer", data={"session_id": sid}, files=files).json()
    assert reply["grade"] is None and reply["verdict_text"] == "Noted." and reply["feedback_audio"] is None
    assert reply["transcript"] == "partial dependency"
    review = api.post("/api/end", data={"session_id": sid}).json()["summary"]
    assert review["mode"] == EXAM and review["answered"] == 3
    assert [r["verdict"] for r in review["review"]] == [CORRECT, SKIPPED, SKIPPED]
    assert review["review"][0]["correct_answer"] == QUESTIONS[0]["answer"]


def test_bad_requests_get_clear_errors(api):
    assert api.post("/api/quiz", data={"mode": "learn"}).status_code == 400          # no notes
    assert api.post("/api/quiz", data={"use_sample": "true", "mode": "party"}).status_code == 400
    assert api.post("/api/quiz", data={"use_sample": "true", "language": "xx"}).status_code == 400
    assert api.post("/api/answer", data={"session_id": "nope", "text": "x"}).status_code == 404
