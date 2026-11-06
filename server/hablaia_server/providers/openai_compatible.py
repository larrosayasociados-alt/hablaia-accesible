"""OpenAI-style HTTP adapters.

The same shape is what Mistral documents for https://api.eu.mistral.ai/v1
chat completions, and what OpenAI documents for /audio/transcriptions and
/audio/speech. Keys stay in the environment and are not logged.
"""

from __future__ import annotations

import io
import wave

import aiohttp

from hablaia_server.providers.base import ProviderError


class OpenAISpeech:
    kind = "openai"

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str, model: str) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model

    async def transcribe(self, pcm16_16k: bytes) -> str:
        if not pcm16_16k:
            return ""
        form = aiohttp.FormData()
        form.add_field("file", _wav(pcm16_16k, 16000), filename="audio.wav", content_type="audio/wav")
        form.add_field("model", self._model)
        form.add_field("language", "es")
        try:
            async with self._session.post(
                f"{self._base}/audio/transcriptions",
                data=form,
                headers={"Authorization": f"Bearer {self._key}"},
            ) as response:
                if response.status != 200:
                    raise ProviderError(f"stt_http_{response.status}")
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise ProviderError("stt_network") from exc
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            raise ProviderError("stt_body")
        return text.strip()


class OpenAIModel:
    kind = "openai"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        token_field: str,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._system = system_prompt
        self._token_field = token_field

    async def reply(self, user_text: str, history: list[dict[str, str]]) -> str:
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": self._system}, *history, {"role": "user", "content": user_text}],
        }
        payload[self._token_field] = 120
        try:
            async with self._session.post(
                f"{self._base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
            ) as response:
                if response.status != 200:
                    raise ProviderError(f"llm_http_{response.status}")
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise ProviderError("llm_network") from exc
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("llm_body") from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("llm_empty")
        return text.strip()


class OpenAIVoice:
    kind = "openai"

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str, model: str, voice: str) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._voice = voice

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        payload = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "wav",
        }
        try:
            async with self._session.post(
                f"{self._base}/audio/speech",
                json=payload,
                headers={"Authorization": f"Bearer {self._key}"},
            ) as response:
                if response.status != 200:
                    raise ProviderError(f"tts_http_{response.status}")
                data = await response.read()
        except aiohttp.ClientError as exc:
            raise ProviderError("tts_network") from exc
        return _pcm_from_wav(data)


def _wav(pcm16: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm16)
    return buffer.getvalue()


def _pcm_from_wav(data: bytes) -> tuple[bytes, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                raise ProviderError("tts_format")
            rate = handle.getframerate()
            pcm = handle.readframes(handle.getnframes())
    except wave.Error as exc:
        raise ProviderError("tts_wav") from exc
    if rate <= 0 or not pcm:
        raise ProviderError("tts_wav")
    return pcm, rate
