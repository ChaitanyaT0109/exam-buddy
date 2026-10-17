"""Read study notes into plain text.

Text, Markdown and PDFs with a text layer are read locally. Photos and scanned or handwritten pages are sent to
Sarvam Vision (through the client) to be read.
"""

import io
import re
from pathlib import Path

from pypdf import PdfReader

TEXT_TYPES = {".txt", ".md", ".markdown"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_CHARS = 15_000  # enough for a chapter of notes; keeps prompts small and cheap


class NotesError(ValueError):
    """The notes could not be read or are empty."""


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def load_notes(data: bytes, filename: str, client=None) -> str:
    """Return the notes as clean text, at most MAX_CHARS characters.

    client is a SarvamClient; it is only needed for images and for PDFs without a text layer (scans).
    """
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_TYPES:
        text = data.decode("utf-8", errors="replace")
    elif suffix == ".pdf":
        text = read_pdf(data)
        if len(clean(text)) < 50:  # a scan: no text layer, so read it like a photo
            if client is None:
                raise NotesError("this PDF has no text layer; a Sarvam key is needed to read scanned pages")
            text = client.read_document(data, filename)
    elif suffix in IMAGE_TYPES:
        if client is None:
            raise NotesError("a Sarvam key is needed to read photos of notes")
        text = client.read_document(data, filename)
    else:
        raise NotesError(f"unsupported notes file '{filename}': use .txt, .md, .pdf, .png or .jpg")
    text = clean(text)
    if len(text) < 50:
        raise NotesError("the notes look empty; add at least a paragraph of text")
    return text[:MAX_CHARS]
