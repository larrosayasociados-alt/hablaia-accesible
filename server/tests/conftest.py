from __future__ import annotations

from datetime import datetime, timezone

from hablaia_server.config import load_settings

DEVICE = "aa:bb:cc:dd:ee:ff"
OTHER = "bb:bb:cc:dd:ee:ff"
CLIENT = "11111111-2222-3333-4444-555555555555"
SECRET = "test-secret-value"


def preview_settings(**extra: str):
    env = {
        "HABLAIA_TOKEN_SECRET": SECRET,
        "HABLAIA_DEVICES": DEVICE,
        "HABLAIA_FRAME_PACE_MS": "0",
        "HABLAIA_TTS_PREROLL_MS": "0",
        "HABLAIA_PUBLIC_WS_URL": "ws://127.0.0.1:8787/xiaozhi/v1/",
    }
    env.update(extra)
    return load_settings(env)


def utc(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
