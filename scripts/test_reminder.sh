#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$(mktemp)"
g++ -std=c++17 -Wall -Wextra -Werror \
  -I "$root/firmware/movement_reminder" \
  "$root/firmware/movement_reminder/reminder_clock.cc" \
  "$root/firmware/movement_reminder/reminder_schedule.cc" \
  "$root/firmware/movement_reminder/test_reminder.cc" \
  -o "$out"
"$out"
rm -f "$out"
