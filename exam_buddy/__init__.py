"""Exam Buddy: a voice quiz partner that quizzes you on your own notes, in your language, using Sarvam AI."""

from .grader import Grade, grade_answer, is_skip
from .languages import LANGUAGES
from .notes import load_notes
from .quiz import Question, generate_questions
from .session import QuizSession

__version__ = "0.1.0"
__all__ = ["LANGUAGES", "Grade", "Question", "QuizSession", "generate_questions", "grade_answer", "is_skip",
           "load_notes"]
