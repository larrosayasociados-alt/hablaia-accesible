#!/usr/bin/env bash
# Print the Xiaozhi v2.5.2 commands recorded in docs/HARDWARE.md.
# This script never invokes idf.py, esptool, or a flash operation.
set -euo pipefail

if [[ "${1:-}" == *flash* || "${1:-}" == *erase* ]]; then
  echo "Este script no flashea ni borra la placa." >&2
  exit 2
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
python3 - "$root" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
pin = json.loads((root / "config" / "upstream-pin.json").read_text(encoding="utf-8"))
profile = json.loads((root / "config" / "build-profile.json").read_text(encoding="utf-8"))
board = pin["board"]
print("Cliente oficial: {repository} {tag} {commit}".format(**pin))
print("SDK que el README de ese tag recomienda: ESP-IDF", pin["sdk"]["readme_recommended_branch"])
print("Minimo que ese README declara:", pin["sdk"]["readme_minimum"])
print("El release dice que se construyo con ESP-IDF", pin["sdk"]["release_notes_built_with"])
print()
print("Dentro del clon de ese tag, despues de cargar export.sh de ESP-IDF:")
print(
    "python scripts/build.py {dir} --name {name} --language {language} --wake-word {wake}".format(
        dir=board["dir"],
        name=board["build_name"],
        language=profile["language"],
        wake=profile["wake_word"],
    )
)
print()
print("El README de la placa tambien documenta, y este script no ejecuta:")
print("  idf.py set-target esp32s3")
print("  idf.py menuconfig")
print("  idf.py build")
print("menuconfig: Xiaozhi Assistant / Waveshare ESP32-S3-Touch-LCD-1.54 / Spanish")
print()
print("Antes, en este repositorio: bash scripts/prepare_firmware.sh")
print("La escritura en la placa esta en docs/PRUEBA.md. Este script no la imprime.")
PY
