from __future__ import annotations

from typing import Protocol


class SpeechToText(Protocol):
    kind: str

    async def transcribe(self, pcm16_16k: bytes) -> str: ...


class LanguageModel(Protocol):
    kind: str

    async def reply(self, user_text: str, history: list[dict[str, str]]) -> str: ...


class TextToSpeech(Protocol):
    kind: str

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        """Return mono PCM16 and its sample rate."""


class ProviderError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
