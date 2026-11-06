"""Device allowlist and short-lived websocket tokens.

The client stores `websocket.token` from the OTA JSON. If the token has no
space, websocket_protocol.cc prefixes `Bearer ` before the handshake.
"""

from __future__ import annotations

import hashlib
import hmac
import time


def normalize_device_id(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip().lower().replace("-", "").replace(":", "")
    if len(raw) != 12 or any(char not in "0123456789abcdef" for char in raw):
        return None
    return ":".join(raw[index : index + 2] for index in range(0, 12, 2))


def device_hash(device_id: str) -> str:
    digest = hashlib.sha256(device_id.encode("ascii")).hexdigest()
    return digest[:12]


def issue_token(secret: bytes, device_id: str, *, now: int | None = None, ttl_s: int) -> str:
    issued_at = int(time.time()) if now is None else int(now)
    expires = issued_at + int(ttl_s)
    body = f"v1.{device_id}.{expires}"
    signature = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    token = f"{body}.{signature}"
    if " " in token:
        raise RuntimeError("token must not contain spaces")
    return token


def verify_token(secret: bytes, token: str, *, now: int | None = None) -> str | None:
    current = int(time.time()) if now is None else int(now)
    parts = token.strip().split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return None
    device_id, expires_text, signature = parts[1], parts[2], parts[3]
    if not expires_text.isdigit() or len(signature) != 32:
        return None
    normalized = normalize_device_id(device_id)
    if normalized != device_id:
        return None
    body = f"v1.{device_id}.{expires_text}"
    expected = hmac.new(secret, body.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, signature):
        return None
    if int(expires_text) < current:
        return None
    return device_id


def bearer_token(header: str | None) -> str | None:
    if not header:
        return None
    value = header.strip()
    if value.lower().startswith("bearer "):
        token = value[7:].strip()
    else:
        token = value
    if not token or any(char.isspace() for char in token):
        return None
    return token
