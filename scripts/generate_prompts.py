#!/usr/bin/env python3
"""Check that the embedded Opus bytes are the committed Ogg files.

Regenerate the speech with scripts/generate_prompts.sh. This check does not
need a speech synthesizer: it only proves the C array matches the Ogg bytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "firmware" / "audio"
SOURCE = ROOT / "firmware" / "movement_reminder" / "hablaia_prompts.cc"


def render() -> str:
    lines = ["#include <stdint.h>", "", 'extern "C" {', ""]
    for index in range(4):
        data = (AUDIO / f"hablaia_mover_{index}.ogg").read_bytes()
        if not data.startswith(b"OggS"):
            raise SystemExit(f"hablaia_mover_{index}.ogg is not an Ogg file")
        lines.append(f"extern const uint8_t hablaia_mover_{index}_ogg[] = {{")
        row: list[str] = []
        for byte in data:
            row.append(f"0x{byte:02x}")
            if len(row) == 16:
                lines.append("    " + ", ".join(row) + ",")
                row = []
        if row:
            lines.append("    " + ", ".join(row) + ",")
        lines.append("};")
        lines.append(f"extern const unsigned hablaia_mover_{index}_ogg_len = {len(data)};")
        lines.append("")
    lines.append("}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    expected = render()
    actual = SOURCE.read_text(encoding="utf-8")
    if actual != expected:
        print("hablaia_prompts.cc does not match firmware/audio/*.ogg", file=sys.stderr)
        raise SystemExit(1)
    print("movement prompts match the Ogg files")


if __name__ == "__main__":
    main()
