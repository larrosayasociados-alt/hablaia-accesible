#!/usr/bin/env python3
"""Check the HablaIA prototype profile without compiling or flashing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "config" / "upstream-pin.json"
PROFILE_PATH = ROOT / "config" / "build-profile.json"
PERSONA_PATH = ROOT / "config" / "persona" / "asistente-senior.es.json"
OTA_PATH = ROOT / "config" / "backend" / "ota-response.example.json"
REMINDER_PATH = ROOT / "config" / "reminder" / "daytime.json"
BACKUP_PATH = ROOT / "config" / "stock-backup.json"
DEFAULTS_PATH = ROOT / "firmware" / "movement_reminder" / "reminder_defaults.h"

REQUIRED = (
    PIN_PATH,
    PROFILE_PATH,
    PERSONA_PATH,
    OTA_PATH,
    ROOT / "docs" / "HARDWARE.md",
    ROOT / "docs" / "ARQUITECTURA.md",
    ROOT / "docs" / "PRUEBA.md",
    ROOT / "config" / "backend" / "README.md",
    REMINDER_PATH,
    BACKUP_PATH,
    DEFAULTS_PATH,
)


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must be a JSON object")
    return value


def assert_invalid_host(url: str, label: str) -> None:
    host = url.split("://", 1)[-1].split("/", 1)[0]
    if not host.endswith(".example.invalid") and host != "example.invalid":
        fail(f"{label} must use the reserved example.invalid domain, got {host!r}")


def scan_tree() -> None:
    blocked_fragments = (
        "BEGIN " + "PRIVATE KEY",
        "BEGIN " + "RSA PRIVATE KEY",
        "AK" + "IA",
        "x-access-" + "token",
    )
    production_host = "hablaia" + ".com"
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "third_party", "build"} for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".bin", ".zip", ".ogg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for fragment in blocked_fragments:
            if fragment in text:
                fail(f"{path.relative_to(ROOT)} contains {fragment}")
        if production_host in text.lower():
            fail(f"{path.relative_to(ROOT)} names a production host")


def minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def check_reminder(persona: dict) -> None:
    reminder = load(REMINDER_PATH)
    header = DEFAULTS_PATH.read_text(encoding="utf-8")
    expected = {
        "HABLAIA_ZONE_NAME": reminder["timezone"],
        "HABLAIA_POSIX_TZ": reminder["posix_tz"],
        "HABLAIA_STATUS": reminder["status"],
        "HABLAIA_INTERVAL_MINUTES": str(reminder["interval_minutes"]),
        "HABLAIA_GRACE_MINUTES": str(reminder["grace_minutes"]),
        "HABLAIA_SNOOZE_MINUTES": str(reminder["snooze_minutes"]),
        "HABLAIA_WINDOW_START_MINUTE": f"({minutes(reminder['window_start']) // 60} * 60)",
        "HABLAIA_WINDOW_END_MINUTE": f"({minutes(reminder['window_end']) // 60} * 60)",
    }
    for name, value in expected.items():
        if f'#define {name} "{value}"' not in header and f"#define {name} {value}" not in header:
            fail(f"reminder default {name} does not match daytime.json")
    if reminder["interval_minutes"] != 180:
        fail("the movement reminder must stay on a three-hour interval")
    messages = reminder["messages"]
    if len(messages) != 4:
        fail("the reminder needs four short phrases")
    prompt = persona["system_prompt"]
    if "caminado" not in prompt or "estirado" not in prompt:
        fail("the senior persona must not claim unstated movement")
    banned = ("salud", "ejercicio", "dolor", "médico", "dosis", "diagnóstico", "debe")
    for index, message in enumerate(messages):
        if f'#define HABLAIA_MESSAGE_{index} "{message}"' not in header:
            fail(f"phrase {index} is not the compiled default")
        lowered = message.casefold()
        for word in banned:
            if word in lowered:
                fail(f"phrase {index} contains {word}")
        if len(message) > 80:
            fail(f"phrase {index} is too long for the 240 pixel screen")
    backup = load(BACKUP_PATH)
    if backup.get("bytes") != 16777216 or backup.get("stored_in_repo") is not False:
        fail("stock backup record is wrong")
    if backup.get("sha256") != "037b8878a1ad0e344ffc88eb7f72216364a571f22267c894b7281f35c3ab0095":
        fail("stock backup hash does not match the completed Mac read")
    for path in ROOT.rglob("*"):
        if path.is_file() and path.stat().st_size == 16777216:
            fail(f"private flash image must not be committed: {path}")


def main() -> None:
    for path in REQUIRED:
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")

    pin = load(PIN_PATH)
    profile = load(PROFILE_PATH)
    persona = load(PERSONA_PATH)
    ota = load(OTA_PATH)

    commit = pin.get("commit", "")
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        fail("upstream pin commit is not a full git sha")
    if pin.get("tag") != "v2.5.2":
        fail("upstream pin is not v2.5.2")
    blobs = pin.get("blobs")
    if not isinstance(blobs, dict) or len(blobs) < 5:
        fail("upstream pin has no blob hashes")
    for name, digest in blobs.items():
        if len(digest) != 64:
            fail(f"blob hash for {name} is not sha256")

    if profile.get("language") != "es-ES":
        fail("build profile language is not es-ES")
    if profile.get("wake_word") != "disabled":
        fail("build profile must disable the Chinese wake word")
    if profile.get("board_dir") != pin["board"]["dir"]:
        fail("build profile board does not match the upstream pin")
    if profile.get("custom_board_firmware") is not False:
        fail("profile must keep the official board firmware")
    if profile.get("ota_url_in_repo") is not None:
        fail("profile must not store an OTA URL")

    if persona.get("id") != "asistente-senior":
        fail("persona id is not asistente-senior")
    if persona.get("display_name") != "Asistente senior":
        fail("persona display name is not Asistente senior")
    if persona.get("locale") != "es-ES" or persona.get("applies_on") != "server":
        fail("persona must be es-ES and applied on the server")
    if persona.get("compiled_into_firmware") is not False:
        fail("persona must stay out of the firmware image")
    prompt = persona.get("system_prompt", "")
    for needle in ("usted", "112", "HablaIA Accesible", "Asistente senior"):
        if needle not in prompt:
            fail(f"persona prompt is missing {needle!r}")
    if len(prompt) < 400:
        fail("persona prompt is too short to be the senior assistant instruction")
    check_reminder(persona)

    websocket = ota.get("websocket")
    if not isinstance(websocket, dict):
        fail("OTA example needs a websocket object")
    if "mqtt" in ota:
        fail("OTA example must not include mqtt; v2.5.2 prefers mqtt when both exist")
    if "token" in websocket:
        fail("OTA example must not carry a token, not even a fake one")
    assert_invalid_host(websocket.get("url", ""), "websocket.url")
    firmware = ota.get("firmware", {})
    if firmware.get("url"):
        fail("OTA example must not advertise a firmware download URL")
    if firmware.get("version") != pin["tag"].lstrip("v") and firmware.get("version") != "2.5.2":
        fail("OTA example firmware version drifted from the pin")

    scan_tree()
    print("prototype profile ok")


if __name__ == "__main__":
    main()
