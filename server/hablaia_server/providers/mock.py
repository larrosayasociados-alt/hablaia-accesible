"""Offline stand-in. It does not recognise speech and does not call a model."""

from __future__ import annotations

from hablaia_server.audio import tone_pcm16

PREVIEW_HEARD = "Esto es una prueba del servidor. Todavía no hay reconocimiento."
PREVIEW_REPLY = (
    "Servidor de prueba. El reconocimiento y la voz natural se activan con las claves. "
    "¿Seguimos cuando estén?"
)


class MockSpeech:
    kind = "mock"

    async def transcribe(self, pcm16_16k: bytes) -> str:
        if len(pcm16_16k) < 320:
            return ""
        return PREVIEW_HEARD


class MockModel:
    kind = "mock"

    async def reply(self, user_text: str, history: list[dict[str, str]]) -> str:
        del user_text, history
        return PREVIEW_REPLY


class MockVoice:
    kind = "mock"

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        del text
        return tone_pcm16(24000, 180, frequency=392.0, amplitude=5000), 24000
