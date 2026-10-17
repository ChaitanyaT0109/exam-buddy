"""Languages Exam Buddy can quiz in (Sarvam speech and voice models cover these)."""

LANGUAGES = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "te-IN": "Telugu",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

DEFAULT_LANGUAGE = "en-IN"


def language_name(code: str) -> str:
    if code not in LANGUAGES:
        raise ValueError(f"unsupported language '{code}'; use one of {sorted(LANGUAGES)}")
    return LANGUAGES[code]
