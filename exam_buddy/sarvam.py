"""Thin wrapper around the official Sarvam AI SDK (pip install sarvamai).

Everything Exam Buddy needs from Sarvam lives here, so the rest of the code can be tested with a fake client:
- chat():           Sarvam-105B for making questions and marking answers
- transcribe():     Saaras speech-to-text (code-mixed speech is fine)
- speak():          Bulbul text-to-speech, returned as WAV bytes
- read_document():  Sarvam Doc AI "digitise" for photos and handwritten pages (the engine behind Indus Document Agents)
"""

import base64
import os
import time
from pathlib import Path

from sarvamai import SarvamAI

CHAT_MODEL = "sarvam-105b"
STT_MODEL = "saaras:v3"

# Teaching ("edtech") voices where Bulbul v4 has them; Bulbul v3 voices for the other languages.
VOICES = {
    "en-IN": ("bulbul:v4-flash", "ritu_en_edtech"),
    "hi-IN": ("bulbul:v4-flash", "ritu_hi_edtech"),
    "te-IN": ("bulbul:v4-flash", "kavitha_te_conversation"),
}
FALLBACK_VOICE = ("bulbul:v3", "priya")
TTS_MAX_CHARS = 1500

AUDIO_CODECS = {".webm": "webm", ".wav": "wav", ".mp3": "mp3", ".ogg": "ogg", ".m4a": "x-m4a", ".flac": "flac"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".pdf": "application/pdf"}


class SarvamError(RuntimeError):
    """A Sarvam call failed; the message is safe to show to the user."""


class SarvamClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("SARVAM_API_KEY", "")
        if not key or key == "your-key-here":
            raise SarvamError("SARVAM_API_KEY is not set: copy .env.example to .env and add your key")
        self.sdk = SarvamAI(api_subscription_key=key)

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 3000,
             json_mode: bool = False) -> str:
        # Thinking is on by default and its tokens count towards max_tokens; a quiz needs quick, short replies,
        # so it is switched off (reasoning_effort=None).
        kwargs = {"model": CHAT_MODEL, "messages": messages, "temperature": temperature,
                  "max_tokens": max_tokens, "reasoning_effort": None}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self.sdk.chat.completions(**kwargs)
        except Exception as e:  # network, quota or validation errors from the SDK
            raise SarvamError(f"Sarvam-105B request failed: {e}") from e
        return response.choices[0].message.content or ""

    def transcribe(self, audio: bytes, filename: str = "answer.webm", language: str = "unknown") -> str:
        codec = AUDIO_CODECS.get(Path(filename).suffix.lower(), "webm")
        try:
            response = self.sdk.speech_to_text.transcribe(
                file=(filename, audio), model=STT_MODEL, mode="codemix", language_code=language,
                input_audio_codec=codec)
        except Exception as e:
            raise SarvamError(f"Saaras speech-to-text failed: {e}") from e
        return (response.transcript or "").strip()

    def speak(self, text: str, language: str = "en-IN") -> bytes:
        model, speaker = VOICES.get(language, FALLBACK_VOICE)
        text = text[:TTS_MAX_CHARS]
        for model, speaker in ((model, speaker), FALLBACK_VOICE):
            try:
                response = self.sdk.text_to_speech.convert(
                    text=text, language_code=language, speaker=speaker, model=model, pace=0.95,
                    output_audio_codec="wav")
                return base64.b64decode("".join(response.audios))
            except Exception as e:
                last_error = e
        raise SarvamError(f"Bulbul text-to-speech failed: {last_error}")

    def read_document(self, data: bytes, filename: str, language: str = "en-IN",
                      handwritten: bool = True, timeout: float = 120) -> str:
        """Digitise a photo or scanned page into Markdown with Sarvam Doc AI (start, poll, fetch)."""
        mime = IMAGE_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")
        try:
            job = self.sdk.doc_ai.digitise(file=[(filename, data, mime)], language=language,
                                           content_type="handwritten" if handwritten else "mixed")
            deadline = time.time() + timeout
            status = job.status
            while status not in {"completed", "partially_completed", "failed", "rejected"}:
                if time.time() > deadline:
                    raise SarvamError("reading the notes took too long; try a smaller or clearer photo")
                time.sleep(3)
                status = self.sdk.doc_ai.get_status(job.job_id).status
            if status in {"failed", "rejected"}:
                raise SarvamError(f"Sarvam could not read this document (status: {status})")
            results = self.sdk.doc_ai.get_results(job.job_id, format="md")
        except SarvamError:
            raise
        except Exception as e:
            raise SarvamError(f"Sarvam Doc AI failed: {e}") from e
        pages = [page.content or "" for doc in results.documents for page in doc.pages]
        return "\n\n".join(pages)
