"""Pull a JSON value out of a model reply (which may wrap it in code fences or add a reasoning block)."""

import json
import re


class ModelReplyError(ValueError):
    """The model's reply did not contain the JSON we asked for."""


def extract_json(reply: str):
    text = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ModelReplyError(f"no JSON found in the model reply: {reply[:200]!r}")
