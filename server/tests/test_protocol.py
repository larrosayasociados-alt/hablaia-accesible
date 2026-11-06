from __future__ import annotations

import json
import logging

import pytest
from aiohttp import WSMsgType
from aiohttp.client_exceptions import WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer

from hablaia_server.app import create_app
from hablaia_server.audio import Decoder, encode_pcm16, parse_binary_frame, rms_pcm16, tone_pcm16
from hablaia_server.auth import issue_token
from hablaia_server.clock import device_unix_after_ota, utc_recovered_by_firmware
from hablaia_server.providers.mock import PREVIEW_HEARD, PREVIEW_REPLY
from tests.conftest import CLIENT, DEVICE, OTHER, SECRET, preview_settings, utc

HELLO = {
    "type": "hello",
    "version": 1,
    "features": {"mcp": True},
    "transport": "websocket",
    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
}


def _ota_headers(device: str = DEVICE) -> dict[str, str]:
    return {
        "Device-Id": device,
        "Client-Id": CLIENT,
        "Accept-Language": "es-ES",
        "User-Agent": "esp32-s3-touch-lcd-1.54/2.5.2",
        "Content-Type": "application/json",
    }


async def _collect(ws, timeout: float = 5):
    texts = []
    frames = []
    while True:
        message = await ws.receive(timeout=timeout)
        if message.type == WSMsgType.TEXT:
            payload = json.loads(message.data)
            texts.append(payload)
            if payload.get("type") == "tts" and payload.get("state") == "stop":
                return texts, frames
        elif message.type == WSMsgType.BINARY:
            frames.append(message.data)
        else:
            raise AssertionError(f"unexpected websocket message {message.type}")


def _uplink(silence_ms: int = 840) -> list[bytes]:
    silence = b"\x00\x00" * (16000 * silence_ms // 1000)
    return encode_pcm16(tone_pcm16(16000, 600, amplitude=8000) + silence, 16000)


@pytest.fixture
async def client():
    app = create_app(preview_settings(), now=lambda: utc(2026, 1, 15, 8, 0))
    async with TestClient(TestServer(app)) as http:
        yield http


async def test_ota_issues_websocket_token_and_madrid_offset(client):
    response = await client.post(
        "/xiaozhi/ota/",
        headers=_ota_headers(),
        json={"application": {"version": "2.5.2"}, "board": {"type": "esp32-s3-touch-lcd-1.54"}},
    )
    assert response.status == 200
    body = await response.json()
    assert set(body) == {"firmware", "server_time", "websocket"}
    assert body["firmware"] == {"version": "2.5.2"}
    assert "url" not in body["firmware"]
    assert "mqtt" not in body
    assert body["websocket"]["url"] == "ws://127.0.0.1:8787/xiaozhi/v1/"
    assert body["websocket"]["version"] == 1
    assert " " not in body["websocket"]["token"]
    clock = body["server_time"]
    assert clock["timezone_offset"] == 60
    assert utc_recovered_by_firmware(
        device_unix_after_ota(clock["timestamp"], clock["timezone_offset"]),
        clock["timezone_offset"],
    ) == int(utc(2026, 1, 15, 8, 0).timestamp())


async def test_ota_rejects_unknown_device_without_a_token(client):
    response = await client.post("/xiaozhi/ota", headers=_ota_headers(OTHER), json={})
    assert response.status == 403
    text = await response.text()
    assert "token" not in text
    assert SECRET not in text


async def test_health_is_marked_preview(client):
    response = await client.get("/health")
    assert await response.json() == {"status": "ok", "mode": "preview"}


async def test_websocket_requires_the_device_token(client):
    with pytest.raises(WSServerHandshakeError):
        await client.ws_connect("/xiaozhi/v1/", headers={"Device-Id": DEVICE, "Client-Id": CLIENT})
    expired = issue_token(SECRET.encode(), DEVICE, now=1_000, ttl_s=5)
    with pytest.raises(WSServerHandshakeError):
        await client.ws_connect(
            "/xiaozhi/v1/",
            headers={"Authorization": f"Bearer {expired}", "Device-Id": DEVICE, "Client-Id": CLIENT, "Protocol-Version": "1"},
        )
    foreign = issue_token(SECRET.encode(), OTHER, now=1_700_000_000, ttl_s=3600)
    with pytest.raises(WSServerHandshakeError):
        await client.ws_connect(
            "/xiaozhi/v1/",
            headers={"Authorization": f"Bearer {foreign}", "Device-Id": DEVICE, "Client-Id": CLIENT},
        )


async def test_manual_turn_returns_json_and_opus(client, caplog):
    caplog.set_level(logging.INFO)
    issued = await client.post(
        "/xiaozhi/ota/",
        headers=_ota_headers(),
        json={"application": {"version": "2.5.2"}, "serial_number": "do-not-log-or-echo"},
    )
    token = (await issued.json())["websocket"]["token"]
    packets = _uplink()
    async with client.ws_connect(
        "/xiaozhi/v1/",
        headers={
            "Authorization": f"Bearer {token}",
            "Device-Id": DEVICE.upper(),
            "Client-Id": CLIENT,
            "Protocol-Version": "1",
        },
    ) as ws:
        await ws.send_str(json.dumps(HELLO))
        hello = await ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["transport"] == "websocket"
        assert hello["audio_params"] == {"format": "opus", "sample_rate": 24000, "channels": 1, "frame_duration": 60}
        assert hello["session_id"]
        await ws.send_str(json.dumps({"session_id": hello["session_id"], "type": "listen", "state": "start", "mode": "manual"}))
        for packet in packets[:4]:
            await ws.send_bytes(packet)
        await ws.send_str(json.dumps({"session_id": hello["session_id"], "type": "listen", "state": "stop"}))
        texts, frames = await _collect(ws)
    types = [(item["type"], item.get("state")) for item in texts]
    assert ("stt", None) in types
    assert ("llm", None) in types
    assert ("tts", "start") in types
    assert ("tts", "sentence_start") in types
    assert ("tts", "stop") in types
    assert types.index(("tts", "start")) < types.index(("tts", "stop"))
    stt = next(item for item in texts if item["type"] == "stt")
    sentence = next(item for item in texts if item.get("state") == "sentence_start")
    assert stt["text"] == PREVIEW_HEARD
    assert sentence["text"] == PREVIEW_REPLY
    assert next(item for item in texts if item["type"] == "llm")["emotion"] == "neutral"
    assert frames
    decoder = Decoder(24000)
    pcm = b"".join(decoder.decode(frame) for frame in frames)
    decoder.close()
    assert rms_pcm16(pcm) > 200
    assert token not in caplog.text
    assert SECRET not in caplog.text
    assert packets[0].hex() not in caplog.text
    assert "do-not-log-or-echo" not in caplog.text


async def test_auto_mode_ends_on_silence_without_listen_stop(client):
    issued = await client.post("/xiaozhi/ota/", headers=_ota_headers(), json={"application": {"version": "2.5.2"}})
    token = (await issued.json())["websocket"]["token"]
    async with client.ws_connect(
        "/xiaozhi/v1/",
        headers={"Authorization": token, "Device-Id": DEVICE, "Client-Id": CLIENT, "Protocol-Version": "1"},
    ) as ws:
        await ws.send_str(json.dumps(HELLO))
        hello = await ws.receive_json()
        await ws.send_str(json.dumps({"session_id": hello["session_id"], "type": "listen", "state": "start", "mode": "auto"}))
        # Longer than HABLAIA_VAD_SILENCE_MS so a mid-sentence pause is not the end.
        for packet in _uplink(silence_ms=1600):
            await ws.send_bytes(packet)
        texts, frames = await _collect(ws)
    assert any(item.get("state") == "stop" for item in texts if item["type"] == "tts")
    assert frames


async def test_protocol_version_2_wraps_audio(client):
    issued = await client.post("/xiaozhi/ota/", headers=_ota_headers(), json={})
    token = (await issued.json())["websocket"]["token"]
    packet = encode_pcm16(tone_pcm16(16000, 120, amplitude=8000), 16000)[0]
    wrapped = __import__("hablaia_server.audio", fromlist=["wrap_binary_frame"]).wrap_binary_frame(2, packet, 50)
    async with client.ws_connect(
        "/xiaozhi/v1",
        headers={"Authorization": f"Bearer {token}", "Device-Id": DEVICE, "Client-Id": CLIENT, "Protocol-Version": "2"},
    ) as ws:
        await ws.send_str(json.dumps(HELLO))
        await ws.receive_json()
        await ws.send_str(json.dumps({"type": "listen", "state": "start", "mode": "manual"}))
        await ws.send_bytes(wrapped)
        await ws.send_str(json.dumps({"type": "listen", "state": "stop"}))
        _texts, frames = await _collect(ws)
    assert frames
    kind, payload = parse_binary_frame(2, frames[0])
    assert kind == "opus" and payload


async def test_abort_and_detect_keep_the_socket(client):
    issued = await client.post("/xiaozhi/ota/", headers=_ota_headers(), json={})
    token = (await issued.json())["websocket"]["token"]
    async with client.ws_connect(
        "/xiaozhi/v1/",
        headers={"Authorization": f"Bearer {token}", "Device-Id": DEVICE, "Client-Id": CLIENT, "Protocol-Version": "1"},
    ) as ws:
        await ws.send_str(json.dumps(HELLO))
        hello = await ws.receive_json()
        await ws.send_str(json.dumps({"session_id": hello["session_id"], "type": "abort", "reason": "wake_word_detected"}))
        await ws.send_str(json.dumps({"session_id": hello["session_id"], "type": "listen", "state": "detect", "text": "Hola."}))
        texts, _frames = await _collect(ws)
    assert any(item["type"] == "stt" and item["text"] == "Hola." for item in texts)


async def test_summer_offset_when_the_clock_is_injected():
    app_settings = preview_settings()
    app = create_app(app_settings, now=lambda: utc(2026, 7, 15, 7, 0))
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/xiaozhi/ota/", headers=_ota_headers(), json={"application": {"version": "2.5.2"}})
        body = await response.json()
    assert body["server_time"]["timezone_offset"] == 120
