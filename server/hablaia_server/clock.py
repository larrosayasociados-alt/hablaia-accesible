"""Europe/Madrid offset for the Xiaozhi OTA clock.

The pinned client (xiaozhi-esp32 v2.5.2, main/ota.cc) does:

    ts += timezone_offset * 60 * 1000
    settimeofday(ts / 1000)

`timestamp` is UTC milliseconds. `timezone_offset` is minutes east of UTC.
The HablaIA firmware stores that same integer in NVS `hablaia/ota_tz_min` and
undoes it before the movement reminder:

    utc = device_unix - ota_offset_minutes * 60

Sending Madrid's own offset (60 in CET, 120 in CEST) makes the device clock
read Spain wall time, and the reminder's subtraction brings back real UTC.
The EU transition used here is the one in the firmware: CEST is
[last Sunday of March 01:00 UTC, last Sunday of October 01:00 UTC).
"""

from __future__ import annotations

import calendar
from datetime import datetime, timezone


def last_sunday(year: int, month: int) -> int:
    last_day = calendar.monthrange(year, month)[1]
    weekday = calendar.weekday(year, month, last_day)
    # calendar.weekday: Monday is 0, Sunday is 6.
    return last_day - (weekday + 1) % 7


def is_cest(moment: datetime) -> bool:
    utc = _as_utc(moment)
    start = datetime(utc.year, 3, last_sunday(utc.year, 3), 1, 0, tzinfo=timezone.utc)
    end = datetime(utc.year, 10, last_sunday(utc.year, 10), 1, 0, tzinfo=timezone.utc)
    return start <= utc < end


def madrid_offset_minutes(moment: datetime) -> int:
    return 120 if is_cest(moment) else 60


def server_time(moment: datetime | None = None) -> dict[str, int]:
    """OTA `server_time` object. Timestamp stays in UTC; the offset is separate."""
    utc = _as_utc(moment or datetime.now(timezone.utc))
    timestamp_ms = int(utc.timestamp() * 1000)
    return {
        "timestamp": timestamp_ms,
        "timezone_offset": madrid_offset_minutes(utc),
    }


def device_unix_after_ota(timestamp_ms: int, timezone_offset_minutes: int) -> int:
    """What v2.5.2 stores with settimeofday, in whole seconds."""
    shifted_ms = timestamp_ms + timezone_offset_minutes * 60 * 1000
    return shifted_ms // 1000


def utc_recovered_by_firmware(device_unix: int, timezone_offset_minutes: int) -> int:
    """The subtraction in firmware/movement_reminder/reminder_clock.cc."""
    return device_unix - timezone_offset_minutes * 60


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(timezone.utc)
