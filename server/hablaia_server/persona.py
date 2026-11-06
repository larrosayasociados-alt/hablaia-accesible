"""Load the server-side Asistente senior profile.

The JSON is the same ficha the firmware branch keeps at
config/persona/asistente-senior.es.json. The model does not read the flash.
This process adds config/persona/server-addendum.es.txt and then cuts the
spoken reply to voice.max_spoken_sentences.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


class PersonaError(RuntimeError):
    pass


@dataclass(frozen=True)
class Persona:
    system_prompt: str
    max_sentences: int
    locale: str
    display_name: str


def load_persona(persona_path: Path, addendum_path: Path) -> Persona:
    try:
        data = json.loads(persona_path.read_text(encoding="utf-8"))
        addendum = addendum_path.read_text(encoding="utf-8").strip()
    except (OSError, json.JSONDecodeError) as exc:
        raise PersonaError(f"cannot read persona files: {exc.__class__.__name__}") from exc
    if data.get("id") != "asistente-senior" or data.get("applies_on") != "server":
        raise PersonaError("persona file is not the server-side Asistente senior profile")
    if data.get("locale") != "es-ES" or data.get("address") != "usted":
        raise PersonaError("persona must be es-ES and address the person as usted")
    if data.get("compiled_into_firmware") is not False:
        raise PersonaError("persona must stay off the firmware image")
    prompt = str(data.get("system_prompt") or "").strip()
    if len(prompt) < 40 or not addendum:
        raise PersonaError("persona prompt is incomplete")
    voice = data.get("voice") if isinstance(data.get("voice"), dict) else {}
    limit = voice.get("max_spoken_sentences", 3)
    if not isinstance(limit, int) or not 1 <= limit <= 3:
        raise PersonaError("max_spoken_sentences must be 1, 2 or 3")
    return Persona(
        system_prompt=prompt + "\n\n" + addendum,
        max_sentences=limit,
        locale=data["locale"],
        display_name=str(data.get("display_name") or "Asistente senior"),
    )


_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_DIGITS = re.compile(r"\d(?:[\s-]?\d){3,}")


def redact_sensitive(text: str) -> str:
    """Drop long digit runs before they are spoken or stored."""
    cleaned = _DIGITS.sub("…", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def limit_sentences(text: str, maximum: int) -> str:
    parts = [part.strip() for part in _SENTENCE.findall(text.strip()) if part.strip()]
    if not parts:
        return ""
    return " ".join(parts[:maximum]).strip()


def prepare_spoken(text: str, maximum: int) -> str:
    spoken = limit_sentences(redact_sensitive(text), maximum)
    if len(spoken) > 400:
        spoken = spoken[:400].rsplit(" ", 1)[0].strip()
    return spoken
