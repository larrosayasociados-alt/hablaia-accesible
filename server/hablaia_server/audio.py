"""Opus frames for the Xiaozhi binary channel, via libopus 1.4.

Version 1, the default in websocket_protocol.h, is one raw Opus packet per
WebSocket binary frame. Versions 2 and 3 add the packed headers from protocol.h.
Downlink frames are 60 ms, which is OPUS_FRAME_DURATION_MS in audio_service.h.
"""

from __future__ import annotations

import ctypes
import math
import struct
from ctypes import c_int, c_int32, c_ubyte, c_void_p

OPUS_APPLICATION_VOIP = 2048
MAX_PACKET_BYTES = 4000
MAX_FRAME_SAMPLES = 5760  # 120 ms at 48 kHz, the largest Opus frame

_LIB: ctypes.CDLL | None = None


class OpusError(RuntimeError):
    pass


def _lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is not None:
        return _LIB
    try:
        lib = ctypes.CDLL("libopus.so.0")
    except OSError as exc:
        raise OpusError("libopus.so.0 is not installed") from exc
    lib.opus_get_version_string.restype = ctypes.c_char_p
    lib.opus_encoder_create.argtypes = [c_int32, c_int, c_int, ctypes.POINTER(c_int)]
    lib.opus_encoder_create.restype = c_void_p
    lib.opus_encode.argtypes = [
        c_void_p,
        ctypes.POINTER(ctypes.c_int16),
        c_int,
        ctypes.POINTER(c_ubyte),
        c_int32,
    ]
    lib.opus_encode.restype = c_int32
    lib.opus_encoder_destroy.argtypes = [c_void_p]
    lib.opus_decoder_create.argtypes = [c_int32, c_int, ctypes.POINTER(c_int)]
    lib.opus_decoder_create.restype = c_void_p
    lib.opus_decode.argtypes = [
        c_void_p,
        ctypes.POINTER(c_ubyte),
        c_int32,
        ctypes.POINTER(ctypes.c_int16),
        c_int,
        c_int,
    ]
    lib.opus_decode.restype = c_int
    lib.opus_decoder_destroy.argtypes = [c_void_p]
    _LIB = lib
    return lib


def opus_version() -> str:
    raw = _lib().opus_get_version_string()
    return raw.decode("ascii") if raw else ""


class Encoder:
    def __init__(self, sample_rate: int) -> None:
        error = c_int()
        self._state = _lib().opus_encoder_create(sample_rate, 1, OPUS_APPLICATION_VOIP, ctypes.byref(error))
        if error.value != 0 or not self._state:
            raise OpusError(f"encoder create failed ({error.value})")
        self.sample_rate = sample_rate

    def encode(self, pcm16: bytes, frame_samples: int) -> bytes:
        if len(pcm16) != frame_samples * 2:
            raise OpusError("pcm frame length does not match")
        samples = (ctypes.c_int16 * frame_samples).from_buffer_copy(pcm16)
        out = (c_ubyte * MAX_PACKET_BYTES)()
        size = _lib().opus_encode(self._state, samples, frame_samples, out, MAX_PACKET_BYTES)
        if size < 0:
            raise OpusError(f"encode failed ({size})")
        return bytes(out[:size])

    def close(self) -> None:
        if self._state:
            _lib().opus_encoder_destroy(self._state)
            self._state = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            return


class Decoder:
    def __init__(self, sample_rate: int) -> None:
        error = c_int()
        self._state = _lib().opus_decoder_create(sample_rate, 1, ctypes.byref(error))
        if error.value != 0 or not self._state:
            raise OpusError(f"decoder create failed ({error.value})")
        self.sample_rate = sample_rate

    def decode(self, packet: bytes) -> bytes:
        if not packet:
            raise OpusError("empty packet")
        encoded = (c_ubyte * len(packet)).from_buffer_copy(packet)
        pcm = (ctypes.c_int16 * MAX_FRAME_SAMPLES)()
        count = _lib().opus_decode(self._state, encoded, len(packet), pcm, MAX_FRAME_SAMPLES, 0)
        if count < 0:
            raise OpusError(f"decode failed ({count})")
        return ctypes.string_at(ctypes.addressof(pcm), count * 2)

    def close(self) -> None:
        if self._state:
            _lib().opus_decoder_destroy(self._state)
            self._state = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            return


def encode_pcm16(pcm16: bytes, sample_rate: int, frame_ms: int = 60) -> list[bytes]:
    frame_samples = sample_rate * frame_ms // 1000
    frame_bytes = frame_samples * 2
    if frame_samples <= 0:
        raise OpusError("bad frame size")
    if len(pcm16) % 2:
        pcm16 += b"\x00"
    if len(pcm16) % frame_bytes:
        pcm16 += b"\x00" * (frame_bytes - (len(pcm16) % frame_bytes))
    encoder = Encoder(sample_rate)
    try:
        frames = []
        for offset in range(0, len(pcm16), frame_bytes):
            frames.append(encoder.encode(pcm16[offset : offset + frame_bytes], frame_samples))
        return frames
    finally:
        encoder.close()


def decode_packet(packet: bytes, sample_rate: int) -> bytes:
    decoder = Decoder(sample_rate)
    try:
        return decoder.decode(packet)
    finally:
        decoder.close()


def tone_pcm16(sample_rate: int, duration_ms: int, frequency: float = 440.0, amplitude: int = 6000) -> bytes:
    count = sample_rate * duration_ms // 1000
    out = bytearray()
    for index in range(count):
        sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
        out += struct.pack("<h", sample)
    return bytes(out)


def rms_pcm16(pcm16: bytes) -> float:
    if len(pcm16) < 2:
        return 0.0
    count = len(pcm16) // 2
    samples = struct.unpack("<" + "h" * count, pcm16[: count * 2])
    total = sum(sample * sample for sample in samples)
    return math.sqrt(total / count)


def resample_pcm16(pcm16: bytes, source_rate: int, target_rate: int) -> bytes:
    if source_rate == target_rate:
        return pcm16
    if source_rate <= 0 or target_rate <= 0:
        raise OpusError("bad sample rate")
    count = len(pcm16) // 2
    if count == 0:
        return b""
    samples = struct.unpack("<" + "h" * count, pcm16[: count * 2])
    target_count = max(1, int(count * target_rate / source_rate))
    out = bytearray()
    for index in range(target_count):
        position = index * source_rate / target_rate
        left = int(position)
        frac = position - left
        right = min(left + 1, count - 1)
        left = min(left, count - 1)
        mixed = int(samples[left] + (samples[right] - samples[left]) * frac)
        mixed = max(-32768, min(32767, mixed))
        out += struct.pack("<h", mixed)
    return bytes(out)


def parse_binary_frame(version: int, data: bytes) -> tuple[str, bytes]:
    """Return ("opus", packet) or ("json", utf-8 payload)."""
    if version == 1:
        if not data or len(data) > 8192:
            raise OpusError("rejected binary frame")
        return "opus", data
    if version == 2:
        if len(data) < 16:
            raise OpusError("short binary v2 frame")
        _version, message_type, _reserved, _timestamp, size = struct.unpack_from("!HHIII", data)
        if size < 0 or size > 8192 or size != len(data) - 16 or message_type not in (0, 1):
            raise OpusError("rejected binary v2 frame")
        payload = data[16 : 16 + size]
        return ("json" if message_type == 1 else "opus"), payload
    if version == 3:
        if len(data) < 4:
            raise OpusError("short binary v3 frame")
        message_type, _reserved, size = struct.unpack_from("!BBH", data)
        if size > 8192 or size != len(data) - 4 or message_type not in (0, 1):
            raise OpusError("rejected binary v3 frame")
        payload = data[4 : 4 + size]
        return ("json" if message_type == 1 else "opus"), payload
    raise OpusError("unsupported protocol version")


def wrap_binary_frame(version: int, packet: bytes, timestamp_ms: int = 0) -> bytes:
    if version == 1:
        return packet
    if version == 2:
        header = struct.pack("!HHIII", 2, 0, 0, timestamp_ms & 0xFFFFFFFF, len(packet))
        return header + packet
    if version == 3:
        header = struct.pack("!BBH", 0, 0, len(packet))
        return header + packet
    raise OpusError("unsupported protocol version")
