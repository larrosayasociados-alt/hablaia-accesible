from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

import pytest

from hablaia_server.audio import (
    Decoder,
    encode_pcm16,
    parse_binary_frame,
    tone_pcm16,
    wrap_binary_frame,
    rms_pcm16,
)
from hablaia_server.auth import bearer_token, issue_token, normalize_device_id, verify_token
from hablaia_server.clock import (
    device_unix_after_ota,
    madrid_offset_minutes,
    server_time,
    utc_recovered_by_firmware,
)
from hablaia_server.config import ConfigError, load_settings
from hablaia_server.logsafe import install, redact
from hablaia_server.ota import build_ota_body, firmware_version
from hablaia_server.persona import limit_sentences, load_persona, prepare_spoken, redact_sensitive
from hablaia_server.vad import EnergyGate
from tests.conftest import DEVICE, SECRET, preview_settings, utc


def test_madrid_offset_matches_zoneinfo_and_firmware_math():
    samples = [
        utc(2026, 1, 15, 8, 0),
        utc(2026, 7, 15, 7, 0),
        utc(2026, 3, 29, 0, 30),
        utc(2026, 3, 29, 1, 0),
        utc(2026, 3, 29, 1, 30),
        utc(2026, 10, 25, 0, 30),
        utc(2026, 10, 25, 1, 0),
    ]
    madrid = ZoneInfo("Europe/Madrid")
    for moment in samples:
        offset = madrid_offset_minutes(moment)
        zonal = moment.astimezone(madrid).utcoffset()
        assert zonal is not None
        assert offset == int(zonal.total_seconds() // 60)
        payload = server_time(moment)
        assert payload["timezone_offset"] == offset
        assert payload["timestamp"] == int(moment.timestamp() * 1000)
        device_unix = device_unix_after_ota(payload["timestamp"], offset)
        recovered = utc_recovered_by_firmware(device_unix, offset)
        assert recovered == int(moment.timestamp())


def test_winter_and_summer_values_documented_for_the_reminder():
    assert madrid_offset_minutes(utc(2026, 1, 15, 8, 0)) == 60
    assert madrid_offset_minutes(utc(2026, 7, 15, 7, 0)) == 120


def test_opus_roundtrip_and_binary_headers():
    original = tone_pcm16(16000, 600, amplitude=8000)
    packets = encode_pcm16(original, 16000)
    decoder = Decoder(16000)
    pcm = b"".join(decoder.decode(packet) for packet in packets)
    decoder.close()
    assert rms_pcm16(pcm) > 1000
    for version in (2, 3):
        wrapped = wrap_binary_frame(version, packets[0], timestamp_ms=1234)
        kind, payload = parse_binary_frame(version, wrapped)
        assert kind == "opus"
        assert payload == packets[0]
    kind, payload = parse_binary_frame(1, packets[0])
    assert kind == "opus" and payload == packets[0]
    import struct

    body = b'{"type":"listen","state":"stop"}'
    frame = struct.pack("!HHIII", 2, 1, 0, 0, len(body)) + body
    assert parse_binary_frame(2, frame) == ("json", body)


def test_tokens_bind_the_device_and_expire():
    secret = SECRET.encode()
    token = issue_token(secret, DEVICE, now=1_700_000_000, ttl_s=60)
    assert " " not in token
    assert verify_token(secret, token, now=1_700_000_010) == DEVICE
    assert verify_token(secret, token, now=1_700_000_061) is None
    assert verify_token(secret, token[:-1] + ("0" if token[-1] != "0" else "1"), now=1_700_000_010) is None
    assert bearer_token("Bearer " + token) == token
    assert bearer_token(token) == token
    assert bearer_token("Bearer two words") is None
    assert normalize_device_id("AA-BB-CC-DD-EE-FF") == DEVICE


def test_ota_body_has_no_firmware_url_and_no_mqtt():
    moment = utc(2026, 1, 15, 8, 0)
    body = build_ota_body(version="2.5.2", moment=moment, ws_url="ws://127.0.0.1:8787/xiaozhi/v1/", token="v1.example")
    assert "url" not in body["firmware"]
    assert "mqtt" not in body
    assert body["websocket"]["version"] == 1
    assert body["server_time"]["timezone_offset"] == 60
    assert firmware_version({"application": {"version": "2.5.2"}}) == "2.5.2"
    assert firmware_version({"application": {"version": "latest"}}) == "2.5.2"


def test_persona_limits_and_redacts_numbers():
    persona = load_persona(preview_settings().persona_path, preview_settings().addendum_path)
    assert "Asistente senior" in persona.system_prompt
    assert "de usted" in persona.system_prompt
    assert "tarjetas" in persona.system_prompt
    assert persona.max_sentences == 3
    spoken = prepare_spoken(
        "La cuenta es 4111 1111 1111 1111. Primera. Segunda. Tercera. Cuarta que no debe salir.",
        3,
    )
    assert "4111" not in spoken
    assert "Cuarta" not in spoken
    assert redact_sensitive("1234") == "…"
    assert limit_sentences("Una. Dos. Tres. Cuatro.", 3).count(".") == 3


def test_config_refuses_public_site_and_open_allowlist():
    with pytest.raises(ConfigError):
        load_settings({"HABLAIA_PUBLIC_WS_URL": "wss://voice.hablaia.com/xiaozhi/v1/"})
    with pytest.raises(ConfigError):
        load_settings({"HABLAIA_PUBLIC_WS_URL": "wss://api.tenclass.net/xiaozhi/v1/"})
    with pytest.raises(ConfigError):
        load_settings(
            {
                "HABLAIA_BIND": "0.0.0.0:8787",
                "HABLAIA_ALLOW_ANY_DEVICE": "1",
                "HABLAIA_PUBLIC_WS_URL": "wss://voice.example/xiaozhi/v1/",
            }
        )
    settings = preview_settings()
    assert SECRET not in repr(settings)


def test_log_redaction():
    token = issue_token(SECRET.encode(), DEVICE, now=1_700_000_000, ttl_s=60)
    assert token not in redact(f"Authorization: Bearer {token} api_key=abc")
    assert "[redacted]" in redact("api_key=abc")
    install()
    record = logging.LogRecord("hablaia.test", logging.INFO, __file__, 1, "Bearer %s", (token,), None)
    assert logging.getLogger().filter(record)
    assert token not in record.getMessage()


def test_energy_gate_waits_for_a_real_pause():
    gate = EnergyGate()
    assert gate.silence_needed >= 18
    assert gate.feed(20) is False
    for _ in range(gate.min_speech_frames):
        assert gate.feed(900) is False
    for _ in range(gate.silence_needed - 1):
        assert gate.feed(10) is False
    assert gate.feed(10) is True


def test_playback_keeps_a_cushion_under_the_device_queue():
    from hablaia_server.pace import DEVICE_DECODE_QUEUE, PlaybackClock

    clock = PlaybackClock(0.06, 8)
    now = 0.0
    high = 0.0
    for _ in range(40):
        now += clock.wait_before(now)
        clock.note_sent(now)
        high = max(high, clock.queued(now))
        assert clock.queued(now) <= DEVICE_DECODE_QUEUE - 4
    assert high <= 8.01
    stalled = PlaybackClock(0.06, 8)
    for _ in range(8):
        stalled.note_sent(0.0)
    assert stalled.wait_before(0.0) == pytest.approx(0.06)
    assert stalled.wait_before(2.0) == 0.0
