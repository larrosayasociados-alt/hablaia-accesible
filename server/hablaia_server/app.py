"""HTTP OTA and the Xiaozhi WebSocket. Preview only: nothing here is a public launch."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import aiohttp
from aiohttp import web

from hablaia_server.auth import bearer_token, issue_token, normalize_device_id, verify_token
from hablaia_server.config import Settings
from hablaia_server.ota import build_ota_body, firmware_version
from hablaia_server.persona import Persona, load_persona
from hablaia_server.providers import Pipeline, build_pipeline
from hablaia_server.session import Session

log = logging.getLogger("hablaia.app")

SETTINGS: web.AppKey[Settings] = web.AppKey("settings", Settings)
PERSONA: web.AppKey[Persona] = web.AppKey("persona", Persona)
PIPELINE: web.AppKey[Pipeline | None] = web.AppKey("pipeline", Pipeline | None)
NOW: web.AppKey = web.AppKey("now")
HTTP: web.AppKey[aiohttp.ClientSession] = web.AppKey("http", aiohttp.ClientSession)


def create_app(settings: Settings, *, now=None, pipeline: Pipeline | None = None) -> web.Application:
    persona = load_persona(settings.persona_path, settings.addendum_path)
    app = web.Application(client_max_size=65536)
    app[SETTINGS] = settings
    app[PERSONA] = persona
    app[PIPELINE] = pipeline
    app[NOW] = now or (lambda: datetime.now(timezone.utc))
    app.on_startup.append(_startup)
    app.on_cleanup.append(_cleanup)
    app.router.add_get("/health", health)
    app.router.add_post("/xiaozhi/ota/", ota)
    app.router.add_post("/xiaozhi/ota", ota)
    app.router.add_get("/xiaozhi/v1/", websocket)
    app.router.add_get("/xiaozhi/v1", websocket)
    return app


async def _startup(app: web.Application) -> None:
    app[HTTP] = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))
    if app[PIPELINE] is None:
        app[PIPELINE] = build_pipeline(app[SETTINGS], app[HTTP], app[PERSONA])


async def _cleanup(app: web.Application) -> None:
    session = app.get(HTTP)
    if session is not None:
        await session.close()


async def health(_: web.Request) -> web.Response:
    return _json({"status": "ok", "mode": "preview"})


async def ota(request: web.Request) -> web.Response:
    settings: Settings = request.app[SETTINGS]
    device_id = normalize_device_id(request.headers.get("Device-Id"))
    if device_id is None:
        return _json({"error": "device"}, status=400)
    if not _client_allowed(settings, request.headers.get("Client-Id")):
        log.info("ota denied reason=client device=%s", device_id)
        return _json({"error": "device"}, status=403)
    if not _device_allowed(settings, device_id):
        log.info("ota denied reason=allowlist device=%s", device_id)
        return _json({"error": "device"}, status=403)
    raw = await request.content.read(65537)
    if len(raw) > 65536:
        return _json({"error": "body"}, status=413)
    body: object = {}
    if raw.strip():
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return _json({"error": "json"}, status=400)
    moment = request.app[NOW]()
    token = issue_token(settings.token_secret, device_id, now=int(time.time()), ttl_s=settings.token_ttl_s)
    payload = build_ota_body(
        version=firmware_version(body),
        moment=moment,
        ws_url=settings.public_ws_url,
        token=token,
    )
    clock = payload["server_time"]
    log.info(
        "ota ok device=%s firmware=%s timezone_offset=%s ua=%s lang=%s",
        device_id,
        payload["firmware"]["version"],
        clock["timezone_offset"],
        request.headers.get("User-Agent", "")[:80],
        request.headers.get("Accept-Language", "")[:32],
    )
    return _json(payload)


async def websocket(request: web.Request) -> web.StreamResponse:
    settings: Settings = request.app[SETTINGS]
    token = bearer_token(request.headers.get("Authorization"))
    device_id = normalize_device_id(request.headers.get("Device-Id"))
    verified = verify_token(settings.token_secret, token, now=int(time.time())) if token else None
    if device_id is None or verified != device_id or not _device_allowed(settings, device_id):
        log.info("ws denied device=%s", device_id or "none")
        return web.Response(status=401, text="unauthorized")
    if not _client_allowed(settings, request.headers.get("Client-Id")):
        log.info("ws denied reason=client device=%s", device_id)
        return web.Response(status=401, text="unauthorized")
    version_text = request.headers.get("Protocol-Version", "1").strip()
    version = int(version_text) if version_text in {"1", "2", "3"} else 1
    pipeline = request.app[PIPELINE]
    if pipeline is None:
        return web.Response(status=503, text="unavailable")
    socket = web.WebSocketResponse(heartbeat=20, max_msg_size=65536)
    await socket.prepare(request)
    persona: Persona = request.app[PERSONA]
    log.info("ws open device=%s protocol=%s", device_id, version)
    await Session(socket, settings, pipeline, persona, device_id, version).run()
    log.info("ws closed device=%s", device_id)
    return socket


def _device_allowed(settings: Settings, device_id: str) -> bool:
    if settings.allow_any_device:
        return True
    return device_id in settings.devices


def _client_allowed(settings: Settings, client_id: str | None) -> bool:
    if not settings.client_ids:
        return True
    return bool(client_id) and client_id.strip().lower() in settings.client_ids


def _json(payload: dict, status: int = 200) -> web.Response:
    return web.json_response(payload, status=status, dumps=lambda value: json.dumps(value, separators=(",", ":")))
