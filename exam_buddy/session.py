"""One quiz round: the questions, the mode, where the student is, and the score.

Two modes:
- learn: feedback after every answer; one hint per question, which caps that question at half a mark.
- exam:  timed, no hints, no feedback until the end, then a full review.
"""

import time
import uuid
from dataclasses import dataclass, field

from .grader import CORRECT, PARTIAL, SKIPPED, Grade, grade_answer
from .quiz import Question, generate_questions

LEARN, EXAM = "learn", "exam"
MODES = {LEARN, EXAM}
EXAM_SECONDS_PER_QUESTION = 60
HINT_CAP = 0.5


@dataclass
class Attempt:
    question: Question
    answer: str
    grade: Grade
    hinted: bool = False
    seconds: float = 0.0
    late: bool = False

    @property
    def points(self) -> float:
        return min(self.grade.points, HINT_CAP) if self.hinted else self.grade.points


@dataclass
class QuizSession:
    questions: list[Question]
    language: str = "en-IN"
    mode: str = LEARN
    seconds_per_question: int = EXAM_SECONDS_PER_QUESTION
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attempts: list[Attempt] = field(default_factory=list)
    hinted: set = field(default_factory=set)
    asked_at: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode '{self.mode}'; use 'learn' or 'exam'")

    @classmethod
    def from_notes(cls, client, notes: str, n: int = 5, language: str = "en-IN", mode: str = LEARN,
                   seconds_per_question: int = EXAM_SECONDS_PER_QUESTION) -> "QuizSession":
        if mode not in MODES:
            raise ValueError(f"unknown mode '{mode}'; use 'learn' or 'exam'")
        return cls(generate_questions(client, notes, n, language), language, mode, seconds_per_question)

    @property
    def done(self) -> bool:
        return len(self.attempts) >= len(self.questions)

    @property
    def current(self) -> Question | None:
        return None if self.done else self.questions[len(self.attempts)]

    @property
    def time_limit(self) -> int:
        return self.seconds_per_question * len(self.questions) if self.mode == EXAM else 0

    def hint(self) -> str:
        """A hint for the current question (learning mode only): the memory aid written with the question."""
        question = self.current
        if question is None:
            raise ValueError("the quiz is already finished")
        if self.mode == EXAM:
            raise PermissionError("no hints in exam mode")
        self.hinted.add(question.id)
        if question.explanation:
            return f"Hint: {question.explanation}"
        topic = question.topic.rstrip("?.! ")
        return f"Hint: think about {topic}."

    def submit(self, client, answer: str) -> Grade:
        question = self.current
        if question is None:
            raise ValueError("the quiz is already finished")
        seconds = time.monotonic() - self.asked_at
        grade = grade_answer(client, question, answer, self.language)
        late = self.mode == EXAM and seconds > self.seconds_per_question + 5  # 5 s grace for speech processing
        self.attempts.append(Attempt(question, answer, grade, question.id in self.hinted, round(seconds, 1), late))
        self.asked_at = time.monotonic()
        return grade

    def summary(self) -> dict:
        score = sum(a.points for a in self.attempts)
        total = len(self.questions)
        weak = [a.question.topic for a in self.attempts if a.points < 1]
        return {
            "mode": self.mode,
            "score": score,
            "total": total,
            "percent": round(100 * score / total) if total else 0,
            "answered": len(self.attempts),
            "correct": sum(a.grade.verdict == CORRECT for a in self.attempts),
            "partial": sum(a.grade.verdict == PARTIAL for a in self.attempts),
            "skipped": sum(a.grade.verdict == SKIPPED for a in self.attempts),
            "hints_used": sum(a.hinted for a in self.attempts),
            "late_answers": sum(a.late for a in self.attempts),
            "topics_to_revise": list(dict.fromkeys(weak)),
            "review": [{"number": i + 1, "question": a.question.question, "your_answer": a.answer,
                        "verdict": a.grade.verdict, "points": a.points, "feedback": a.grade.feedback,
                        "correct_answer": a.question.answer, "explanation": a.question.explanation,
                        "hinted": a.hinted, "seconds": a.seconds, "late": a.late}
                       for i, a in enumerate(self.attempts)],
        }
