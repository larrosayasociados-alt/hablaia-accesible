#!/usr/bin/env bash
# Clone the pinned Xiaozhi tag and apply the HablaIA reminder. Does not flash.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
pin="$(python3 -c 'import json; print(json.load(open("'"$root"'/config/upstream-pin.json"))["commit"])')"
tag="$(python3 -c 'import json; print(json.load(open("'"$root"'/config/upstream-pin.json"))["tag"])')"
dest="$root/third_party/xiaozhi-esp32"
if [[ ! -d "$dest/.git" ]]; then
  git clone --depth 1 --branch "$tag" https://github.com/78/xiaozhi-esp32.git "$dest"
fi
if [[ "$(git -C "$dest" rev-parse HEAD)" != "$pin" ]]; then
  echo "third_party/xiaozhi-esp32 is $(git -C "$dest" rev-parse HEAD), expected $pin" >&2
  exit 1
fi
python3 "$root/scripts/apply_hablaia.py" --tree "$dest"
echo "Tree ready at $dest"
echo "Load ESP-IDF release/v6.1, then run the build.py command from scripts/print_build.sh"
