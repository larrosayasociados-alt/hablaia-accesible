"""JSON messages the v2.5.2 client actually dispatches.

application.cc reads tts start/stop/sentence_start, stt text, and llm emotion.
Binary audio is queued only while the device state is already speaking, and
tts start is applied on the main loop, so the server waits briefly and then
sends Opus at about one frame per 60 ms.
"""

from __future__ import annotations

DOWNLINK_SAMPLE_RATE = 24000
FRAME_MS = 60
UPLINK_SAMPLE_RATE = 16000


def server_hello(session_id: str) -> dict:
    return {
        "type": "hello",
        "transport": "websocket",
        "session_id": session_id,
        "audio_params": {
            "format": "opus",
            "sample_rate": DOWNLINK_SAMPLE_RATE,
            "channels": 1,
            "frame_duration": FRAME_MS,
        },
    }


def stt_message(session_id: str, text: str) -> dict:
    return {"session_id": session_id, "type": "stt", "text": text}


def llm_message(session_id: str) -> dict:
    return {"session_id": session_id, "type": "llm", "emotion": "neutral", "text": "neutral"}


def tts_message(session_id: str, state: str, text: str | None = None) -> dict:
    message = {"session_id": session_id, "type": "tts", "state": state}
    if text is not None:
        message["text"] = text
    return message
