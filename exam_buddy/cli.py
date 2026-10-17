"""Exam Buddy in the terminal (typed answers):  exam-buddy notes.md --count 5 --lang en-IN --mode learn"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from .languages import LANGUAGES
from .notes import load_notes
from .sarvam import SarvamClient, SarvamError
from .session import EXAM, LEARN, QuizSession

VERDICT = {"correct": "Correct!", "partial": "Partly correct.", "incorrect": "Not quite.", "skipped": "Skipped."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Quiz yourself on your notes with Sarvam AI.")
    parser.add_argument("notes", type=Path, help="notes file: .md, .txt, .pdf, or a photo of handwritten notes")
    parser.add_argument("--count", type=int, default=5, help="number of questions (1-10)")
    parser.add_argument("--lang", default="en-IN", choices=sorted(LANGUAGES), help="quiz language")
    parser.add_argument("--mode", default=LEARN, choices=[LEARN, EXAM], help="learn: feedback each time; exam: review at the end")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        client = SarvamClient()
        notes = load_notes(args.notes.read_bytes(), args.notes.name, client)
        print("Writing questions from your notes...")
        session = QuizSession.from_notes(client, notes, args.count, args.lang, args.mode)
    except (SarvamError, OSError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    print(f"\n{len(session.questions)} questions, {'exam' if args.mode == EXAM else 'learning'} mode. "
          "Type your answer, 'hint' (learning mode) or 'skip'.\n")
    while not session.done:
        q = session.current
        print(f"Q{len(session.attempts) + 1}. [{q.topic}] {q.question}")
        answer = input("> ").strip()
        if answer.lower() == "hint" and args.mode == LEARN:
            print("Hint:", session.hint())
            answer = input("> ").strip()
        grade = session.submit(client, answer)
        if args.mode == LEARN:
            print(f"{VERDICT[grade.verdict]} {grade.feedback}\nAnswer: {grade.correct_answer}\n")
        else:
            print("Noted.\n")

    s = session.summary()
    print(f"Score: {s['score']} / {s['total']} ({s['percent']}%)")
    if args.mode == EXAM:
        for r in s["review"]:
            print(f"  {r['number']}. {VERDICT[r['verdict']]} {r['correct_answer']}")
    if s["topics_to_revise"]:
        print("Revise:", ", ".join(s["topics_to_revise"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
