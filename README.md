# Exam Buddy

**Your notes. Your language. A quiz partner that talks.**

Exam Buddy turns your own study notes (typed, PDF, or a photo of handwritten pages) into a spoken quiz. It asks
questions out loud in English, Hindi or another Indian language, listens to your spoken answer (mixing languages
is fine), marks it, and tells you what to revise. Built at **Sarvam Campus '26 x IIIT Hyderabad** on
[Sarvam AI](https://www.sarvam.ai/)'s models and the **Indus** platform.

## Two ways to practise

| | Learning mode | Exam mode |
|---|---|---|
| Feedback | after every answer: verdict, the right answer, a one-line reason | none until the end ("Noted.") |
| Hints | one per question (caps that question at half a mark) | none |
| Time | no limit | 60 seconds per question, live countdown |
| End | score and topics to revise | full review of every question, score, % and topics to revise |

### Marking

| Verdict | Marks | When |
|---|---|---|
| Correct | 1 | every key idea of the model answer is there, in any wording or language |
| Partly correct | 0.5 | some key idea is there, but something important is missing or slightly off |
| Not quite | 0 | the key idea is missing or wrong, or only keywords are listed, or the answer contradicts itself |
| Skipped | 0 | "I don't know", "skip", "pass" (English or Hindi), or time ran out in exam mode |

A hint caps that question at half a mark. Skipped answers are detected without calling the model, so they can
never be marked by mistake.

## How it uses Sarvam

| Step | Sarvam model |
|---|---|
| Read photos and handwritten notes | **Sarvam Vision** (Doc AI digitise, 22 Indian languages) |
| Write the questions and model answers | **Sarvam-105B** (JSON mode) |
| Ask the question out loud | **Bulbul** text-to-speech (edtech voices for English and Hindi) |
| Hear your answer | **Saaras** speech-to-text (code-mixed speech) |
| Mark the answer and explain | **Sarvam-105B** |

The same quiz also runs as an **Indus Voice Agent** (no code, built with Genie) with the notes as its knowledge
base: see [docs/indus-agent.md](docs/indus-agent.md) for the full agent setup, guardrails and tests.

## Run it

You need Python 3.10+ and a Sarvam API key (from [indus.sarvam.ai](https://indus.sarvam.ai)).

```bash
git clone https://github.com/ChaitanyaT0109/exam-buddy.git
cd exam-buddy
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env          # macOS / Linux: cp .env.example .env   then put your key in .env
uvicorn exam_buddy.server:app --port 8200
```

Open http://localhost:8200, pick your notes (or the sample DBMS notes), a mode and a language, and press
**Start quiz**. Allow the microphone and tap it to answer.

**Live voice agent (optional).** To put your Indus Voice Agent on the page (the round call button), add its IDs
and a Voice Agents API key to `.env` (`INDUS_APP_ID`, `INDUS_ORG_ID`, `INDUS_WORKSPACE_ID`, `INDUS_API_KEY`; see
`.env.example`). The page uses Sarvam's `<sarvam-widget>` with `session-endpoint="/api/sarvam/"`: the browser asks
our server for a short-lived session, and the server adds the key, so the key never reaches the browser.

**Deploy (Docker).** The `Dockerfile` runs the web app on `$PORT` (default 8200). Set `SARVAM_API_KEY` (and the
optional `INDUS_*` values) in your host's secret settings. Every endpoint has a per-visitor limit (for example 6
new quizzes and 10 live-call sessions a minute) and notes uploads are capped at 10 MB, so a public link cannot
burn through your Sarvam credits quickly. The microphone only works over HTTPS (or on localhost).

```bash
docker build -t exam-buddy .
docker run -p 8200:8200 --env-file .env exam-buddy
```

**Terminal version** (typed answers):

```bash
exam-buddy notes/sample-dbms-normalization.md --count 5 --lang hi-IN --mode exam
```

**As a library:**

```python
from exam_buddy import QuizSession, load_notes
from exam_buddy.sarvam import SarvamClient

client = SarvamClient()                       # reads SARVAM_API_KEY
notes = load_notes(open("notes.pdf", "rb").read(), "notes.pdf", client)
quiz = QuizSession.from_notes(client, notes, n=5, language="en-IN", mode="learn")
print(quiz.current.question)
grade = quiz.submit(client, "2NF removes partial dependencies")
print(grade.verdict, grade.feedback, quiz.summary()["score"])
```

## Project layout

```
exam_buddy/
  sarvam.py     the only file that talks to Sarvam (chat, speech-to-text, text-to-speech, Doc AI)
  notes.py      text, PDF or photo -> clean notes text
  quiz.py       notes -> questions with model answers (Sarvam-105B)
  grader.py     marking rules, skip detection, safe fallback
  session.py    learning / exam mode, hints, timing, score and review
  server.py     FastAPI app (the key stays on the server)
  cli.py        terminal quiz
web/            one-page voice UI (mic recording, timers, review)
docs/           the Indus Voice Agent setup
tests/          19 tests with a fake Sarvam client (no network, no credits)
```

Run the tests with `pytest`.

## Privacy

- The Sarvam key stays on the server in `.env` (git-ignored); the browser never sees it.
- Notes and answers are kept in memory only for the quiz you are taking; nothing is written to disk or logged.
- Exam Buddy never asks for personal details.

## Limits

- Questions and marking come from a language model, so double-check anything important against your textbook.
- One spoken answer can be at most about 25 seconds (the speech API takes 30 seconds per request).
- Quizzes are kept in memory, so restarting the server ends them.

## License

MIT, see [LICENSE](LICENSE).
