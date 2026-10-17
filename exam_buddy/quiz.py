"""Make quiz questions from notes with Sarvam-105B."""

from dataclasses import asdict, dataclass

from .jsonutil import ModelReplyError, extract_json
from .languages import language_name

MAX_QUESTIONS = 10


@dataclass
class Question:
    id: int
    question: str
    answer: str
    explanation: str
    topic: str
    difficulty: str  # easy | medium | hard

    def to_dict(self) -> dict:
        return asdict(self)


QUESTION_PROMPT = """You are an examiner making a short spoken quiz from a student's notes.

Write exactly {n} questions in {language}. Rules:
- Every question must be answerable from the notes alone, in one or two sentences. No multiple choice.
- Go from easy to hard. Cover different parts of the notes; never repeat an idea.
- Keep each question under 25 words: it will be read aloud.
- Technical terms may stay in English.
- "answer" is the model answer in one or two sentences, in {language}.
- "explanation" is one simple sentence that helps the student remember, in {language}.
- "topic" is a short English label for the part of the notes (2-4 words).

Reply with ONLY a JSON object, no other text:
{{"questions": [{{"question": "...", "answer": "...", "explanation": "...", "topic": "...", "difficulty": "easy|medium|hard"}}]}}

NOTES:
\"\"\"
{notes}
\"\"\"
"""


def parse_questions(reply: str, n: int) -> list[Question]:
    data = extract_json(reply)
    if isinstance(data, dict):  # some replies wrap the list: {"questions": [...]}
        data = next((v for v in data.values() if isinstance(v, list)), [])
    questions = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        question, answer = str(item.get("question", "")).strip(), str(item.get("answer", "")).strip()
        if not question or not answer:
            continue
        difficulty = str(item.get("difficulty", "medium")).lower()
        questions.append(Question(
            id=len(questions) + 1,
            question=question,
            answer=answer,
            explanation=str(item.get("explanation", "")).strip(),
            topic=str(item.get("topic", "General")).strip() or "General",
            difficulty=difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
        ))
    if not questions:
        raise ModelReplyError("the model returned no usable questions")
    return questions[:n]


def generate_questions(client, notes: str, n: int = 5, language: str = "en-IN") -> list[Question]:
    """Ask Sarvam-105B for n questions; one retry if the reply is not usable JSON."""
    n = max(1, min(n, MAX_QUESTIONS))
    prompt = QUESTION_PROMPT.format(n=n, language=language_name(language), notes=notes)
    messages = [{"role": "user", "content": prompt}]
    try:
        return parse_questions(client.chat(messages, temperature=0.4, json_mode=True), n)
    except ModelReplyError:
        messages.append({"role": "user", "content": "Reply again with ONLY the JSON object, nothing else."})
        return parse_questions(client.chat(messages, temperature=0.2, json_mode=True), n)
