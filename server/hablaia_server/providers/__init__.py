"""Build the speech, model and voice stages selected by the environment."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from hablaia_server.config import ProviderSpec, Settings
from hablaia_server.persona import Persona
from hablaia_server.providers.azure_speech import AzureSpeech, AzureVoice
from hablaia_server.providers.base import LanguageModel, SpeechToText, TextToSpeech
from hablaia_server.providers.mock import MockModel, MockSpeech, MockVoice
from hablaia_server.providers.openai_compatible import OpenAIModel, OpenAISpeech, OpenAIVoice


@dataclass
class Pipeline:
    stt: SpeechToText
    llm: LanguageModel
    tts: TextToSpeech

    @property
    def label(self) -> str:
        return f"stt={self.stt.kind} llm={self.llm.kind} tts={self.tts.kind}"


def build_pipeline(settings: Settings, http: aiohttp.ClientSession, persona: Persona) -> Pipeline:
    return Pipeline(
        stt=_stt(settings.stt, http),
        llm=_llm(settings.llm, http, persona.system_prompt),
        tts=_tts(settings.tts, http),
    )


def _stt(spec: ProviderSpec, http: aiohttp.ClientSession) -> SpeechToText:
    if spec.kind == "mock":
        return MockSpeech()
    if spec.kind == "openai":
        return OpenAISpeech(http, spec.base_url, spec.api_key, spec.model)
    if spec.kind == "azure":
        return AzureSpeech(http, spec.region, spec.api_key, spec.language)
    raise RuntimeError("unknown stt provider")


def _llm(spec: ProviderSpec, http: aiohttp.ClientSession, system_prompt: str) -> LanguageModel:
    if spec.kind == "mock":
        return MockModel()
    if spec.kind == "openai":
        return OpenAIModel(http, spec.base_url, spec.api_key, spec.model, system_prompt, spec.token_field)
    raise RuntimeError("unknown llm provider")


def _tts(spec: ProviderSpec, http: aiohttp.ClientSession) -> TextToSpeech:
    if spec.kind == "mock":
        return MockVoice()
    if spec.kind == "openai":
        return OpenAIVoice(http, spec.base_url, spec.api_key, spec.model, spec.voice)
    if spec.kind == "azure":
        return AzureVoice(http, spec.region, spec.api_key, spec.voice, spec.language)
    raise RuntimeError("unknown tts provider")
