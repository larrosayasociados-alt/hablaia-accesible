#!/usr/bin/env python3
"""Copy the HablaIA reminder into a Xiaozhi v2.5.2 tree and patch three call sites.

The patch keeps the official Waveshare board file, the talk button, and the
partition table. It does not flash.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "49b4380b3faa0ceadd28a3e78aaf0f311c46c57e"
RAW = "https://raw.githubusercontent.com/78/xiaozhi-esp32/{commit}/{path}"

REPLACEMENTS = {
    "main/CMakeLists.txt": [
        (
            '            "application.cc"\n',
            '            "application.cc"\n'
            '            "hablaia/reminder_clock.cc"\n'
            '            "hablaia/reminder_schedule.cc"\n'
            '            "hablaia/hablaia_prompts.cc"\n'
            '            "hablaia/hablaia_reminder.cc"\n',
        )
    ],
    "main/application.cc": [
        (
            '#include "application.h"\n',
            '#include "application.h"\n#include "hablaia/hablaia_reminder.h"\n',
        ),
        (
            "    esp_timer_start_periodic(clock_timer_handle_, 1000000);\n",
            "    esp_timer_start_periodic(clock_timer_handle_, 1000000);\n"
            "    HablaiaReminder_Init();\n",
        ),
        (
            "            if (clock_ticks_ % 10 == 0) {\n"
            "                SystemInfo::PrintHeapStats();\n"
            "                // SystemInfo::PrintTaskList();\n"
            "                // SystemInfo::PrintTaskCpuUsage(pdMS_TO_TICKS(1000));\n"
            "            }\n",
            "            if (clock_ticks_ % 10 == 0) {\n"
            "                SystemInfo::PrintHeapStats();\n"
            "                // SystemInfo::PrintTaskList();\n"
            "                // SystemInfo::PrintTaskCpuUsage(pdMS_TO_TICKS(1000));\n"
            "            }\n"
            "            HablaiaReminder_OnClockTick(has_server_time_, "
            "GetDeviceState() == kDeviceStateIdle);\n",
        ),
    ],
    "main/ota.cc": [
        (
            "            if (cJSON_IsNumber(timezone_offset)) {\n"
            "                ts += (timezone_offset->valueint * 60 * 1000); // 转换分钟为毫秒\n"
            "            }\n",
            "            int hablaia_offset_min = 0;\n"
            "            if (cJSON_IsNumber(timezone_offset)) {\n"
            "                hablaia_offset_min = timezone_offset->valueint;\n"
            "                ts += (hablaia_offset_min * 60 * 1000); // 转换分钟为毫秒\n"
            "            }\n",
        ),
        (
            "            settimeofday(&tv, NULL);\n"
            "            has_server_time_ = true;\n",
            "            settimeofday(&tv, NULL);\n"
            "            has_server_time_ = true;\n"
            "            Settings hablaia_time(\"hablaia\", true);\n"
            "            hablaia_time.SetInt(\"ota_tz_min\", hablaia_offset_min);\n"
            "            hablaia_time.SetBool(\"time_ok\", true);\n",
        ),
    ],
    "main/boards/waveshare/esp32-s3-touch-lcd-1.54/esp32-s3-touch-lcd-1.54.cc": [
        (
            '#include "power_manager.h"\n',
            '#include "power_manager.h"\n#include "hablaia/hablaia_reminder.h"\n',
        ),
        (
            "            pwr_button_.OnClick([this]() {\n"
            "                auto& app = Application::GetInstance();\n"
            "                app.ToggleChatState();\n"
            "            });\n",
            "            pwr_button_.OnClick([this]() {\n"
            "                auto& app = Application::GetInstance();\n"
            "                HablaiaReminder_OnTalk();\n"
            "                app.ToggleChatState();\n"
            "            });\n",
        ),
        (
            "        volume_up_button_.OnClick([this]() {\n"
            "            auto codec = Board::GetInstance().GetAudioCodec();\n",
            "        volume_up_button_.OnClick([this]() {\n"
            "            if (HablaiaReminder_OnVolumeUp()) {\n"
            "                return;\n"
            "            }\n"
            "            auto codec = Board::GetInstance().GetAudioCodec();\n",
        ),
        (
            "        volume_down_button_.OnClick([this]() {\n"
            "            auto codec = Board::GetInstance().GetAudioCodec();\n",
            "        volume_down_button_.OnClick([this]() {\n"
            "            if (HablaiaReminder_OnVolumeDown()) {\n"
            "                return;\n"
            "            }\n"
            "            auto codec = Board::GetInstance().GetAudioCodec();\n",
        ),
    ],
}

COPY_FILES = [
    ROOT / "firmware/movement_reminder/reminder_clock.cc",
    ROOT / "firmware/movement_reminder/reminder_schedule.cc",
    ROOT / "firmware/movement_reminder/reminder_schedule.h",
    ROOT / "firmware/movement_reminder/reminder_defaults.h",
    ROOT / "firmware/movement_reminder/hablaia_prompts.cc",
    ROOT / "firmware/movement_reminder/hablaia_prompts.h",
    ROOT / "firmware/port/hablaia_reminder.cc",
    ROOT / "firmware/port/hablaia_reminder.h",
]


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def apply_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if new in text:
            continue
        count = text.count(old)
        if count != 1:
            fail(f"{path}: expected one match, found {count} for {old[:80]!r}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def copy_sources(tree: Path) -> None:
    destination = tree / "main" / "hablaia"
    destination.mkdir(parents=True, exist_ok=True)
    for source in COPY_FILES:
        shutil.copy2(source, destination / source.name)


def apply_tree(tree: Path) -> None:
    if not (tree / "main" / "application.cc").is_file():
        fail(f"{tree} is not a Xiaozhi tree")
    copy_sources(tree)
    for relative, replacements in REPLACEMENTS.items():
        apply_text(tree / relative, replacements)


def fetch(path: str) -> str:
    url = RAW.format(commit=PIN, path=path)
    request = urllib.request.Request(url, headers={"User-Agent": "hablaia-accesible"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def check_against_pin() -> None:
    for relative, replacements in REPLACEMENTS.items():
        text = fetch(relative)
        for old, new in replacements:
            if text.count(old) != 1:
                fail(f"pin {PIN} no longer contains the anchor in {relative}")
            text = text.replace(old, new, 1)
        if "HablaiaReminder_Init" not in text and relative.endswith("application.cc"):
            fail("application patch did not insert the reminder")
        if "hablaia_time" not in text and relative.endswith("ota.cc"):
            fail("ota patch did not record the timezone offset")
        if "HablaiaReminder_OnTalk" not in text and relative.endswith(".cc") and "touch-lcd" in relative:
            fail("board patch did not keep the talk button")
        if "hablaia/hablaia_reminder.cc" not in text and relative.endswith("CMakeLists.txt"):
            fail("CMake patch did not add the reminder sources")
    print(f"hablaia patch matches xiaozhi {PIN}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, help="Xiaozhi checkout to modify")
    parser.add_argument("--check", action="store_true", help="Check anchors at the pinned commit")
    args = parser.parse_args()
    if args.check:
        check_against_pin()
        return
    if args.tree is None:
        fail("pass --tree or --check")
    apply_tree(args.tree)
    print(f"applied HablaIA reminder to {args.tree}")


if __name__ == "__main__":
    main()
