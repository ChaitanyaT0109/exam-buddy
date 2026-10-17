"""Exam Buddy web app: FastAPI backend + a one-page voice UI (web/).

Run:  uvicorn exam_buddy.server:app --port 8200   then open http://localhost:8200
The Sarvam key stays on the server (SARVAM_API_KEY in .env); the browser never sees it.
"""

import base64
import os
import re
import time
from collections import OrderedDict
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .grader import CORRECT, PARTIAL, SKIPPED
from .jsonutil import ModelReplyError
from .languages import LANGUAGES
from .notes import NotesError, load_notes
from .sarvam import SarvamClient, SarvamError
from .session import EXAM, LEARN, MODES, QuizSession

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SAMPLE_NOTES = ROOT / "notes" / "sample-dbms-normalization.md"
MAX_SESSIONS = 200          # quizzes live in memory only; the oldest are dropped first
MAX_AUDIO_BYTES = 2_000_000  # about 25 s of browser audio

load_dotenv(ROOT / ".env")
app = FastAPI(title="Exam Buddy", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")
SESSIONS: "OrderedDict[str, QuizSession]" = OrderedDict()
_client: SarvamClient | None = None

VERDICT_WORDS = {
    "en-IN": {CORRECT: "Correct!", PARTIAL: "Partly correct.", "incorrect": "Not quite.", SKIPPED: "No problem."},
    "hi-IN": {CORRECT: "सही जवाब!", PARTIAL: "आधा सही।", "incorrect": "पूरी तरह सही नहीं।", SKIPPED: "कोई बात नहीं।"},
}
ANSWER_LEAD = {"en-IN": "The answer is:", "hi-IN": "सही उत्तर है:"}


def client() -> SarvamClient:
    global _client
    if _client is None:
        load_dotenv(ROOT / ".env")  # picks up a key added after the server started
        try:
            _client = SarvamClient()
        except SarvamError as e:
            raise HTTPException(503, str(e)) from e
    return _client


def audio_b64(text: str, language: str) -> str | None:
    """Spoken version of text; the quiz still works (text only) if text-to-speech fails."""
    try:
        return base64.b64encode(client().speak(text, language)).decode()
    except (SarvamError, HTTPException):
        return None


def question_payload(session: QuizSession) -> dict | None:
    question = session.current
    if question is None:
        return None
    return {"number": len(session.attempts) + 1, "total": len(session.questions), "id": question.id,
            "text": question.question, "topic": question.topic, "difficulty": question.difficulty,
            "audio": audio_b64(question.question, session.language)}


MAX_NOTES_BYTES = 10_000_000  # 10 MB per notes upload
_hits: dict[tuple[str, str], list[float]] = {}


def rate_limit(request: Request, bucket: str, per_minute: int) -> None:
    """Simple per-visitor limit, so a public deployment cannot burn through the Sarvam credits."""
    visitor = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _hits.get((bucket, visitor), []) if now - t < 60]
    if len(recent) >= per_minute:
        raise HTTPException(429, "too many requests; please wait a minute and try again")
    _hits[(bucket, visitor)] = recent + [now]


def get_session(session_id: str) -> QuizSession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(404, "this quiz has expired; start a new one")
    return session


# ---- Live voice agent (Sarvam Indus) --------------------------------------------------------------------------
# The page shows Sarvam's <sarvam-widget> call button with session-endpoint="/api/sarvam/". The widget calls our
# endpoint, we add the API key and pass the request on to Sarvam's app runtime, so the key never reaches the browser.
INDUS_RUNTIME = "https://apps.sarvam.ai/api/app-runtime/"
INDUS_PATH = re.compile(r"^[A-Za-z0-9_\-/.]*$")
INDUS_RATE = 10  # session requests per minute per visitor


def indus_ids() -> dict | None:
    """The agent's public IDs from .env (INDUS_APP_ID is required; org and workspace IDs are optional)."""
    load_dotenv(ROOT / ".env")
    app_id = os.environ.get("INDUS_APP_ID", "").strip()
    if not app_id or "paste" in app_id:
        return None
    return {"app_id": app_id, "org_id": os.environ.get("INDUS_ORG_ID", "").strip(),
            "workspace_id": os.environ.get("INDUS_WORKSPACE_ID", "").strip()}


@app.api_route("/api/sarvam/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def indus_session(path: str, request: Request):
    if indus_ids() is None:
        raise HTTPException(404, "the live voice agent is not set up on this server")
    if ".." in path or not INDUS_PATH.match(path):
        raise HTTPException(400, "bad path")
    rate_limit(request, "live", INDUS_RATE)
    headers = {"X-API-Key": os.environ.get("INDUS_API_KEY") or os.environ.get("SARVAM_API_KEY", "")}
    if request.headers.get("content-type"):
        headers["Content-Type"] = request.headers["content-type"]
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            upstream = await http.request(request.method, INDUS_RUNTIME + path, params=request.query_params,
                                          content=await request.body(), headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"could not reach Sarvam: {e}") from e
    return Response(upstream.content, status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"))


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/config")
def config():
    try:
        client()
        ready = True
    except HTTPException:
        ready = False
    return {"languages": LANGUAGES, "sarvam_ready": ready, "sample": SAMPLE_NOTES.stem, "indus": indus_ids()}


@app.post("/api/quiz")
async def start_quiz(request: Request, language: str = Form("en-IN"), count: int = Form(5),
                     mode: str = Form(LEARN), notes_text: str = Form(""), use_sample: bool = Form(False),
                     file: UploadFile | None = File(None)):
    rate_limit(request, "quiz", 6)
    if language not in LANGUAGES:
        raise HTTPException(400, f"unsupported language '{language}'")
    if mode not in MODES:
        raise HTTPException(400, "mode must be 'learn' or 'exam'")
    started = time.perf_counter()
    try:
        if file is not None and file.filename:
            data = await file.read()
            if len(data) > MAX_NOTES_BYTES:
                raise HTTPException(413, "the notes file is too large; keep it under 10 MB")
            notes = load_notes(data, file.filename, client())
        elif notes_text.strip():
            notes = load_notes(notes_text.encode(), "notes.txt")
        elif use_sample:
            notes = load_notes(SAMPLE_NOTES.read_bytes(), SAMPLE_NOTES.name)
        else:
            raise HTTPException(400, "add your notes: upload a file, paste text, or use the sample notes")
        session = QuizSession.from_notes(client(), notes, count, language, mode)
    except NotesError as e:
        raise HTTPException(400, str(e)) from e
    except (SarvamError, ModelReplyError) as e:
        raise HTTPException(502, f"Sarvam could not make the quiz: {e}") from e
    SESSIONS[session.id] = session
    while len(SESSIONS) > MAX_SESSIONS:
        SESSIONS.popitem(last=False)
    question = question_payload(session)
    session.asked_at = time.monotonic()  # the clock starts once the first question is ready
    return {"session_id": session.id, "language": language, "mode": mode, "notes_chars": len(notes),
            "seconds_per_question": session.seconds_per_question if mode == EXAM else None,
            "question": question, "seconds": round(time.perf_counter() - started, 1)}


@app.post("/api/hint")
def hint(request: Request, session_id: str = Form(...)):
    rate_limit(request, "hint", 20)
    session = get_session(session_id)
    try:
        text = session.hint()
    except PermissionError as e:
        raise HTTPException(403, "no hints in exam mode") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"hint": text, "audio": audio_b64(text, session.language), "note": "a hint caps this question at 1/2 mark"}


@app.post("/api/end")
def end_exam(request: Request, session_id: str = Form(...)):
    """Finish early: every unanswered question counts as skipped (no model calls), then the review."""
    rate_limit(request, "end", 10)
    session = get_session(session_id)
    while not session.done:
        session.submit(client(), "")
    return {"summary": session.summary()}


@app.post("/api/answer")
async def answer(request: Request, session_id: str = Form(...), text: str = Form(""),
                 audio: UploadFile | None = File(None)):
    rate_limit(request, "answer", 40)
    session = get_session(session_id)
    if session.done:
        raise HTTPException(400, "this quiz is finished")
    transcript = text.strip()
    if audio is not None and audio.filename:
        data = await audio.read()
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "the recording is too long; keep answers under 25 seconds")
        try:
            transcript = client().transcribe(data, audio.filename, "unknown")
        except SarvamError as e:
            raise HTTPException(502, str(e)) from e
    question = session.current
    try:
        grade = session.submit(client(), transcript)
    except SarvamError as e:
        raise HTTPException(502, str(e)) from e
    next_question = question_payload(session)
    session.asked_at = time.monotonic()  # the next question's clock starts after its audio is ready
    summary_data = session.summary() if session.done else None
    if session.mode == EXAM:
        # exam mode: no marks, no answers, no feedback until the review
        return {"transcript": transcript, "grade": None, "verdict_text": "Noted.", "feedback_audio": None,
                "next_question": next_question, "summary": summary_data}
    words = VERDICT_WORDS.get(session.language, VERDICT_WORDS["en-IN"])
    lead = ANSWER_LEAD.get(session.language, ANSWER_LEAD["en-IN"])
    spoken = f"{words[grade.verdict]} {grade.feedback} {lead} {question.answer}".strip()
    return {"transcript": transcript, "grade": grade.to_dict(), "verdict_text": words[grade.verdict],
            "capped_by_hint": question.id in session.hinted,
            "feedback_audio": audio_b64(spoken, session.language),
            "next_question": next_question, "summary": summary_data}


@app.get("/api/summary/{session_id}")
def summary(session_id: str):
    return get_session(session_id).summary()
