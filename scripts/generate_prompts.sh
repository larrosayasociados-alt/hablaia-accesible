#!/usr/bin/env bash
# Rebuild the four Spanish prompts. Requires pico2wave and ffmpeg with libopus.
# The committed Ogg files are what the device plays; this script is the recipe.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/firmware/audio"
mkdir -p "$out"
phrases=(
  "Si le parece, dé unos pasos a su ritmo."
  "Puede estirarse un momento, con suavidad."
  "Un pequeño paseo, solo si le apetece."
  "Si quiere, mueva los hombros con calma."
)
for i in 0 1 2 3; do
  wav="$(mktemp --suffix .wav)"
  pico2wave -l es-ES -w "$wav" "${phrases[$i]}"
  ffmpeg -y -loglevel error -i "$wav" -c:a libopus -b:a 24k -ar 16000 -ac 1 \
    -frame_duration 60 -application voip "$out/hablaia_mover_$i.ogg"
  rm -f "$wav"
done
python3 - << PY
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("generate_prompts", "$root/scripts/generate_prompts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Path("$root/firmware/movement_reminder/hablaia_prompts.cc").write_text(module.render(), encoding="utf-8")
PY
python3 "$root/scripts/generate_prompts.py"
