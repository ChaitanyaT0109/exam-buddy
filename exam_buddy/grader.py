"""Mark a student's spoken answer against the model answer."""

import re
from dataclasses import asdict, dataclass

from .jsonutil import ModelReplyError, extract_json
from .languages import language_name
from .quiz import Question

CORRECT, PARTIAL, INCORRECT, SKIPPED = "correct", "partial", "incorrect", "skipped"
POINTS = {CORRECT: 1.0, PARTIAL: 0.5, INCORRECT: 0.0, SKIPPED: 0.0}

# "I don't know" in English and Hindi (typed, spoken or transliterated); these never need the model.
SKIP_PATTERNS = [
    r"^\s*(skip|pass|next)\b",
    r"\bi\s*(do\s*not|don'?t|dont)\s*know\b",
    r"\bno\s*idea\b",
    r"\bpata\s*nahi\b", r"\bnahi\s*pata\b", r"\bmaloom\s*nahi\b",
    r"पता\s*नहीं", r"नहीं\s*पता", r"मालूम\s*नहीं",
]


@dataclass
class Grade:
    verdict: str        # correct | partial | incorrect | skipped
    feedback: str       # what was right or missing, spoken to the student
    correct_answer: str
    explanation: str

    @property
    def points(self) -> float:
        return POINTS[self.verdict]

    def to_dict(self) -> dict:
        return {**asdict(self), "points": self.points}


GRADE_PROMPT = """You are a kind examiner marking a student's spoken answer. The answer came from speech
recognition, so ignore spelling, grammar and filler words; judge only the idea.

Question: {question}
Model answer: {answer}
Student's answer: {student}

Verdict:
- "correct" if the key idea of the model answer is present, even in different words or another language.
- "partial" if only part of the key idea is present.
- "incorrect" if the key idea is missing or wrong.

"feedback" is at most 25 words in {language}, warm and specific: say what was right and what was missing.
Never use the word "wrong".

Reply with ONLY JSON: {{"verdict": "correct|partial|incorrect", "feedback": "..."}}
"""


def is_skip(answer: str) -> bool:
    text = answer.strip().lower()
    return not text or any(re.search(p, text) for p in SKIP_PATTERNS)


def grade_answer(client, question: Question, student_answer: str, language: str = "en-IN") -> Grade:
    if is_skip(student_answer):
        return Grade(SKIPPED, "No problem, here is the answer.", question.answer, question.explanation)
    prompt = GRADE_PROMPT.format(question=question.question, answer=question.answer,
                                 student=student_answer.strip(), language=language_name(language))
    try:
        data = extract_json(client.chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=400,
                                        json_mode=True))
        verdict = str(data.get("verdict", "")).lower().strip()
        feedback = str(data.get("feedback", "")).strip()
    except (ModelReplyError, AttributeError):
        verdict, feedback = "", ""
    if verdict not in {CORRECT, PARTIAL, INCORRECT}:
        # never guess a mark: if the model reply is unusable, fall back to "partial" with a neutral note
        verdict, feedback = PARTIAL, "I could not mark this one clearly, so compare with the model answer."
    return Grade(verdict, feedback, question.answer, question.explanation)
