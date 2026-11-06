"""Azure Speech REST in a chosen region.

STT uses the short-audio conversation endpoint and `language=es-ES`.
TTS uses SSML against the regional cognitiveservices/v1 endpoint and asks
for riff-24khz-16bit-mono-pcm. West Europe is a documented Speech region.
The subscription key is sent as a header and is not written to the log.
"""

from __future__ import annotations

import aiohttp

from hablaia_server.providers.base import ProviderError
from hablaia_server.providers.openai_compatible import _pcm_from_wav, _wav


class AzureSpeech:
    kind = "azure"

    def __init__(self, session: aiohttp.ClientSession, region: str, key: str, language: str) -> None:
        self._session = session
        self._region = region
        self._key = key
        self._language = language

    async def transcribe(self, pcm16_16k: bytes) -> str:
        if not pcm16_16k:
            return ""
        url = (
            f"https://{self._region}.stt.speech.microsoft.com"
            f"/speech/recognition/conversation/cognitiveservices/v1"
            f"?language={self._language}&format=simple"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Accept": "application/json",
        }
        try:
            async with self._session.post(url, data=_wav(pcm16_16k, 16000), headers=headers) as response:
                if response.status != 200:
                    raise ProviderError(f"stt_http_{response.status}")
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise ProviderError("stt_network") from exc
        if not isinstance(body, dict):
            raise ProviderError("stt_body")
        status = body.get("RecognitionStatus")
        if status == "NoMatch":
            return ""
        if status != "Success":
            raise ProviderError("stt_status")
        text = body.get("DisplayText")
        if not isinstance(text, str):
            raise ProviderError("stt_body")
        return text.strip()


class AzureVoice:
    kind = "azure"

    def __init__(self, session: aiohttp.ClientSession, region: str, key: str, voice: str, locale: str) -> None:
        self._session = session
        self._region = region
        self._key = key
        self._voice = voice
        self._locale = locale

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        ssml = (
            f"<speak version='1.0' xml:lang='{self._locale}'>"
            f"<voice xml:lang='{self._locale}' name='{self._voice}'>"
            f"<prosody rate='slow'>{safe}</prosody></voice></speak>"
        )
        url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "hablaia-accesible-preview",
        }
        try:
            async with self._session.post(url, data=ssml.encode("utf-8"), headers=headers) as response:
                if response.status != 200:
                    raise ProviderError(f"tts_http_{response.status}")
                data = await response.read()
        except aiohttp.ClientError as exc:
            raise ProviderError("tts_network") from exc
        return _pcm_from_wav(data)
