"""OTA JSON consumed by xiaozhi-esp32 v2.5.2 main/ota.cc.

The client treats firmware as an update only when both firmware.version and
firmware.url are strings. This preview never sends firmware.url. It also never
sends mqtt: if both mqtt and websocket are present, v2.5.2 keeps MQTT.
"""

from __future__ import annotations

import re
from datetime import datetime

from hablaia_server.clock import server_time

_VERSION = re.compile(r"^\d+(?:\.\d+){1,3}$")


def firmware_version(body: object) -> str:
    if isinstance(body, dict):
        application = body.get("application")
        if isinstance(application, dict):
            version = application.get("version")
            if isinstance(version, str) and _VERSION.fullmatch(version):
                return version
    return "2.5.2"


def build_ota_body(*, version: str, moment: datetime, ws_url: str, token: str) -> dict:
    if not token or " " in token:
        raise RuntimeError("refusing to publish an empty token")
    body = {
        "firmware": {"version": version},
        "server_time": server_time(moment),
        "websocket": {
            "url": ws_url,
            "token": token,
            "version": 1,
        },
    }
    if "url" in body["firmware"] or "mqtt" in body:
        raise RuntimeError("ota body would change the device transport or offer firmware")
    return body
