"""One device WebSocket, from hello through Opus and the JSON turn."""

from __future__ import annotations

import json
import logging
import uuid

from aiohttp import WSMsgType, web

from hablaia_server.audio import (
    Decoder,
    OpusError,
    encode_pcm16,
    parse_binary_frame,
    resample_pcm16,
    rms_pcm16,
    wrap_binary_frame,
)
from hablaia_server.config import Settings
from hablaia_server.messages import (
    DOWNLINK_SAMPLE_RATE,
    FRAME_MS,
    UPLINK_SAMPLE_RATE,
    llm_message,
    server_hello,
    stt_message,
    tts_message,
)
from hablaia_server.persona import Persona, prepare_spoken
from hablaia_server.providers import Pipeline
from hablaia_server.providers.base import ProviderError
from hablaia_server.vad import EnergyGate

log = logging.getLogger("hablaia.session")

MAX_FRAMES = 1000
NOT_HEARD = "No le he oído bien. ¿Puede repetirlo?"
UNAVAILABLE = "Ahora no puedo responder. Inténtelo de nuevo dentro de un momento."
OPUS_RATES = {8000, 12000, 16000, 24000, 48000}


class Session:
    def __init__(
        self,
        ws: web.WebSocketResponse,
        settings: Settings,
        pipeline: Pipeline,
        persona: Persona,
        device_id: str,
        version: int,
    ) -> None:
        self.ws = ws
        self.settings = settings
        self.pipeline = pipeline
        self.persona = persona
        self.device_id = device_id
        self.version = version
        self.session_id = uuid.uuid4().hex
        self.uplink_rate = UPLINK_SAMPLE_RATE
        self.frames: list[bytes] = []
        self.pcm = bytearray()
        self.decoder: Decoder | None = None
        self.gate = EnergyGate()
        self.mode = "manual"
        self.listening = False
        self.welcomed = False
        self.speaking = False
        self.busy = False
        self.generation = 0
        self.ignore_frames = 0
        self.history: list[dict[str, str]] = []

    async def run(self) -> None:
        try:
            first = await self.ws.receive(timeout=10)
        except (TimeoutError, TypeError):
            await self._close(4408, "hello timeout")
            return
        await self._handle(first)
        if not self.welcomed:
            await self._close(4400, "expected hello")
            return
        async for message in self.ws:
            if message.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED}:
                break
            try:
                await self._handle(message)
            except Exception as exc:
                log.info("session step failed session=%s error=%s", self.session_id, exc.__class__.__name__)
        self._close_decoder()

    async def _handle(self, message) -> None:
        if message.type == WSMsgType.TEXT:
            await self._on_text(message.data)
        elif message.type == WSMsgType.BINARY:
            await self._on_binary(message.data)
        elif message.type == WSMsgType.ERROR:
            log.info("websocket error session=%s", self.session_id)

    async def _on_text(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.info("ignored text bytes=%d session=%s", len(raw), self.session_id)
            return
        if not isinstance(data, dict):
            return
        kind = data.get("type")
        if kind == "hello":
            await self._on_hello(data)
        elif kind == "listen":
            await self._on_listen(data)
        elif kind == "abort":
            await self._on_abort()
        elif kind == "mcp":
            log.info("mcp ignored session=%s", self.session_id)
        else:
            log.info("ignored json type=%s session=%s", kind if isinstance(kind, str) else "none", self.session_id)

    async def _on_hello(self, data: dict) -> None:
        transport = data.get("transport")
        if transport not in {None, "websocket"}:
            await self._close(4400, "transport")
            return
        audio = data.get("audio_params") if isinstance(data.get("audio_params"), dict) else {}
        rate = audio.get("sample_rate", UPLINK_SAMPLE_RATE)
        self.uplink_rate = int(rate) if rate in OPUS_RATES else UPLINK_SAMPLE_RATE
        self.welcomed = True
        await self._send(server_hello(self.session_id))
        log.info(
            "hello session=%s device=%s uplink_hz=%s protocol=%s",
            self.session_id,
            self.device_id,
            self.uplink_rate,
            self.version,
        )

    async def _on_listen(self, data: dict) -> None:
        state = data.get("state")
        mode = data.get("mode")
        if isinstance(mode, str) and mode in {"auto", "manual", "realtime"}:
            self.mode = mode
        if state == "start":
            await self._cancel_speech()
            self.listening = True
            self.frames.clear()
            self.pcm.clear()
            self.gate.reset()
            self._reset_decoder()
            log.info("listen start session=%s mode=%s", self.session_id, self.mode)
            return
        if state == "stop":
            frames = len(self.frames)
            self.listening = False
            log.info("listen stop session=%s frames=%d bytes=%d", self.session_id, frames, len(self.pcm))
            if frames == 0 and not self.pcm:
                return
            await self._turn("", rearm=False)
            return
        if state == "detect":
            text = data.get("text") if isinstance(data.get("text"), str) else ""
            log.info("listen detect session=%s chars=%d", self.session_id, len(text))
            await self._cancel_speech()
            self.pcm.clear()
            self.frames.clear()
            await self._turn(text, rearm=False)
            return
        log.info("listen ignored session=%s", self.session_id)

    async def _on_binary(self, data: bytes) -> None:
        try:
            kind, payload = parse_binary_frame(self.version, data)
        except OpusError:
            log.info("rejected binary session=%s bytes=%d", self.session_id, len(data))
            return
        if kind == "json":
            await self._on_text(payload.decode("utf-8", "replace"))
            return
        if self.ignore_frames > 0:
            self.ignore_frames -= 1
            return
        if not self.listening or self.busy:
            return
        if len(self.frames) >= MAX_FRAMES:
            log.info("uplink capped session=%s", self.session_id)
            self.listening = False
            await self._turn("", rearm=self.mode in {"auto", "realtime"})
            return
        self.frames.append(payload)
        decoded = self._decode(payload)
        if decoded:
            self.pcm.extend(decoded)
        if self.mode in {"auto", "realtime"} and decoded and self.gate.feed(rms_pcm16(decoded)):
            log.info("vad end session=%s frames=%d", self.session_id, len(self.frames))
            self.listening = False
            await self._turn("", rearm=True)

    async def _turn(self, seeded_text: str, *, rearm: bool) -> None:
        if self.busy:
            return
        self.busy = True
        self.generation += 1
        generation = self.generation
        pcm = bytes(self.pcm)
        frame_count = len(self.frames)
        self.pcm.clear()
        self.frames.clear()
        self._reset_decoder()
        try:
            heard = prepare_spoken(seeded_text, 3)
            if not heard:
                try:
                    heard = prepare_spoken(await self.pipeline.stt.transcribe(pcm), 3)
                except ProviderError as exc:
                    log.info("stt failed session=%s code=%s", self.session_id, exc.code)
                    heard = ""
            if not heard:
                reply = NOT_HEARD
            else:
                try:
                    reply = await self.pipeline.llm.reply(heard, list(self.history))
                except ProviderError as exc:
                    log.info("llm failed session=%s code=%s", self.session_id, exc.code)
                    reply = UNAVAILABLE
            reply = prepare_spoken(reply, self.persona.max_sentences) or UNAVAILABLE
            if heard and self.pipeline.llm.kind != "mock" and reply != UNAVAILABLE:
                self.history.append({"role": "user", "content": heard[:400]})
                self.history.append({"role": "assistant", "content": reply[:400]})
                del self.history[:-8]
            packets: list[bytes] = []
            try:
                audio, rate = await self.pipeline.tts.synthesize(reply)
                audio = resample_pcm16(audio, rate, DOWNLINK_SAMPLE_RATE)
                if audio:
                    packets = encode_pcm16(audio, DOWNLINK_SAMPLE_RATE, FRAME_MS)
            except (ProviderError, OpusError) as exc:
                log.info("tts failed session=%s code=%s", self.session_id, getattr(exc, "code", "opus"))
            if generation != self.generation or self.ws.closed:
                return
            await self._send(stt_message(self.session_id, heard or NOT_HEARD))
            await self._send(llm_message(self.session_id))
            await self._send(tts_message(self.session_id, "start"))
            self.speaking = True
            await self._send(tts_message(self.session_id, "sentence_start", reply))
            if self.settings.preroll_s:
                await self._sleep(self.settings.preroll_s)
            for index, packet in enumerate(packets):
                if generation != self.generation or self.ws.closed:
                    break
                await self.ws.send_bytes(wrap_binary_frame(self.version, packet, index * FRAME_MS))
                if self.settings.pace_s:
                    await self._sleep(self.settings.pace_s)
            if generation == self.generation and not self.ws.closed:
                await self._send(tts_message(self.session_id, "stop"))
                if rearm and self.mode in {"auto", "realtime"}:
                    self.listening = True
                    self.ignore_frames = 8
                    self.gate.reset()
                    self._reset_decoder()
            self.speaking = False
            log.info(
                "turn done session=%s uplink_frames=%d downlink_frames=%d reply_chars=%d",
                self.session_id,
                frame_count,
                len(packets),
                len(reply),
            )
        finally:
            self.busy = False

    async def _on_abort(self) -> None:
        log.info("abort session=%s", self.session_id)
        await self._cancel_speech()
        self.listening = False
        self.frames.clear()
        self.pcm.clear()

    async def _cancel_speech(self) -> None:
        self.generation += 1
        if self.speaking and not self.ws.closed:
            await self._send(tts_message(self.session_id, "stop"))
        self.speaking = False

    def _decode(self, packet: bytes) -> bytes | None:
        try:
            if self.decoder is None or self.decoder.sample_rate != self.uplink_rate:
                self._reset_decoder()
                self.decoder = Decoder(self.uplink_rate)
            return self.decoder.decode(packet)
        except OpusError as exc:
            log.info("opus decode skipped session=%s detail=%s", self.session_id, str(exc).split("(")[-1].rstrip(")"))
            return None

    def _reset_decoder(self) -> None:
        self._close_decoder()

    def _close_decoder(self) -> None:
        if self.decoder is not None:
            self.decoder.close()
            self.decoder = None

    async def _send(self, payload: dict) -> None:
        await self.ws.send_str(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    async def _close(self, code: int, reason: str) -> None:
        if not self.ws.closed:
            await self.ws.close(code=code, message=reason.encode("ascii", "ignore")[:120])
