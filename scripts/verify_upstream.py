#!/usr/bin/env python3
"""Confirm the pinned Xiaozhi files still match the recorded hashes.

This does not clone ESP-IDF and does not compile or flash firmware.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "config" / "upstream-pin.json"
RAW = "https://raw.githubusercontent.com/78/xiaozhi-esp32/{commit}/{path}"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hablaia-accesible-pin-check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> None:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    commit = pin["commit"]
    mismatches: list[str] = []
    for path, expected in pin["blobs"].items():
        url = RAW.format(commit=commit, path=path)
        payload = fetch(url)
        actual = hashlib.sha256(payload).hexdigest()
        status = "ok" if actual == expected else "MISMATCH"
        print(f"{status} {actual} {path}")
        if actual != expected:
            mismatches.append(path)
        if path.endswith("language.json"):
            document = json.loads(payload)
            locale = document.get("language", {}).get("type")
            if locale != "es-ES":
                mismatches.append(path + " locale")
                print(f"MISMATCH locale {locale!r} in {path}")
        if path.endswith("config.json"):
            document = json.loads(payload)
            name = document["builds"][0]["name"]
            if name != pin["board"]["build_name"]:
                mismatches.append(path + " build name")
                print(f"MISMATCH build name {name!r}")
    if mismatches:
        print("upstream pin drifted: " + ", ".join(mismatches), file=sys.stderr)
        raise SystemExit(1)
    print(f"upstream {pin['tag']} {commit} matches {len(pin['blobs'])} files")


if __name__ == "__main__":
    main()
