"""Environment for the preview server. Real keys are never given defaults."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(RuntimeError):
    pass


def persona_files() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        persona = parent / "config" / "persona" / "asistente-senior.es.json"
        addendum = parent / "config" / "persona" / "server-addendum.es.txt"
        if persona.is_file() and addendum.is_file():
            return persona, addendum
    raise ConfigError("cannot find config/persona next to the server")


_FORBIDDEN_SUFFIXES = (".hablaia.com",)
_FORBIDDEN_HOSTS = {"hablaia.com", "www.hablaia.com", "api.tenclass.net"}


@dataclass(frozen=True)
class ProviderSpec:
    kind: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    voice: str = ""
    region: str = ""
    language: str = "es-ES"
    token_field: str = "max_tokens"

    def public_label(self) -> str:
        if self.kind == "mock":
            return "mock"
        if self.kind == "azure":
            return f"azure region={self.region or 'unset'} voice={self.voice or 'default'}"
        host = urlparse(self.base_url).hostname or "unset"
        return f"openai host={host} model={self.model or 'unset'}"


@dataclass(frozen=True)
class Settings:
    bind_host: str
    bind_port: int
    public_ws_url: str
    token_secret: bytes
    token_ttl_s: int
    devices: frozenset[str]
    client_ids: frozenset[str]
    allow_any_device: bool
    ephemeral_secret: bool
    persona_path: Path
    addendum_path: Path
    stt: ProviderSpec
    llm: ProviderSpec
    tts: ProviderSpec
    pace_s: float
    preroll_s: float
    log_level: str

    def __repr__(self) -> str:
        return (
            f"Settings(bind={self.bind_host}:{self.bind_port}, devices={len(self.devices)}, "
            f"allow_any={self.allow_any_device}, stt={self.stt.kind}, llm={self.llm.kind}, "
            f"tts={self.tts.kind}, ephemeral_secret={self.ephemeral_secret})"
        )


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    host, port = _bind(env.get("HABLAIA_BIND", "127.0.0.1:8787"))
    public = env.get("HABLAIA_PUBLIC_WS_URL", "").strip()
    if not public:
        if host in {"0.0.0.0", "::"}:
            raise ConfigError("HABLAIA_PUBLIC_WS_URL is required when the server listens on all interfaces")
        public = f"ws://127.0.0.1:{port}/xiaozhi/v1/"
    _check_public_url(public)
    allow_any = _bool(env.get("HABLAIA_ALLOW_ANY_DEVICE", "0"))
    if allow_any and host in {"0.0.0.0", "::"}:
        raise ConfigError("HABLAIA_ALLOW_ANY_DEVICE cannot be used when listening on all interfaces")
    secret_text = env.get("HABLAIA_TOKEN_SECRET", "").strip()
    ephemeral = not secret_text
    secret = secret_text.encode("utf-8") if secret_text else secrets.token_bytes(32)
    default_persona, default_addendum = persona_files()
    devices = _devices(env.get("HABLAIA_DEVICES", ""))
    if not devices and not allow_any:
        # An empty allowlist rejects every device. That is the safe default.
        devices = frozenset()
    return Settings(
        bind_host=host,
        bind_port=port,
        public_ws_url=public if public.endswith("/") else public + "/",
        token_secret=secret,
        token_ttl_s=_positive_int(env.get("HABLAIA_TOKEN_TTL_SECONDS", "604800"), "HABLAIA_TOKEN_TTL_SECONDS"),
        devices=devices,
        client_ids=_client_ids(env.get("HABLAIA_CLIENT_IDS", "")),
        allow_any_device=allow_any,
        ephemeral_secret=ephemeral,
        persona_path=Path(env.get("HABLAIA_PERSONA_PATH", str(default_persona))),
        addendum_path=Path(env.get("HABLAIA_ADDENDUM_PATH", str(default_addendum))),
        stt=_stt(env),
        llm=_llm(env),
        tts=_tts(env),
        pace_s=_non_negative_float(env.get("HABLAIA_FRAME_PACE_MS", "60"), "HABLAIA_FRAME_PACE_MS") / 1000,
        preroll_s=_non_negative_float(env.get("HABLAIA_TTS_PREROLL_MS", "200"), "HABLAIA_TTS_PREROLL_MS") / 1000,
        log_level=env.get("HABLAIA_LOG_LEVEL", "INFO").upper(),
    )


def _bind(value: str) -> tuple[str, int]:
    if value.startswith("[") and "]:" in value:
        host, port_text = value[1:].split("]:", 1)
    elif value.count(":") == 1:
        host, port_text = value.split(":", 1)
    else:
        raise ConfigError("HABLAIA_BIND must look like 127.0.0.1:8787")
    if not host:
        raise ConfigError("HABLAIA_BIND is missing a host")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ConfigError("HABLAIA_BIND has a bad port") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("HABLAIA_BIND has a bad port")
    return host, port


def _check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname or parsed.query or parsed.fragment:
        raise ConfigError("HABLAIA_PUBLIC_WS_URL must be a ws:// or wss:// URL")
    if not parsed.path.rstrip("/").endswith("/xiaozhi/v1"):
        raise ConfigError("HABLAIA_PUBLIC_WS_URL path must end in /xiaozhi/v1/")
    host = parsed.hostname.lower().rstrip(".")
    if host in _FORBIDDEN_HOSTS or host.endswith(_FORBIDDEN_SUFFIXES):
        raise ConfigError("HABLAIA_PUBLIC_WS_URL must not use the production site or the stock Xiaozhi host")


def _devices(value: str) -> frozenset[str]:
    from hablaia_server.auth import normalize_device_id

    found = []
    for piece in value.split(","):
        if not piece.strip():
            continue
        device = normalize_device_id(piece)
        if device is None:
            raise ConfigError("HABLAIA_DEVICES contains a value that is not a MAC address")
        found.append(device)
    return frozenset(found)


def _client_ids(value: str) -> frozenset[str]:
    return frozenset(piece.strip().lower() for piece in value.split(",") if piece.strip())


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: str, name: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if number <= 0:
        raise ConfigError(f"{name} must be positive")
    return number


def _non_negative_float(value: str, name: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if number < 0:
        raise ConfigError(f"{name} must be zero or positive")
    return number


def _required(env: dict[str, str], *names: str) -> None:
    missing = [name for name in names if not env.get(name, "").strip()]
    if missing:
        raise ConfigError("missing " + ", ".join(missing))


def _stt(env: dict[str, str]) -> ProviderSpec:
    kind = env.get("HABLAIA_STT_PROVIDER", "mock").strip().lower()
    if kind == "mock":
        return ProviderSpec("mock")
    if kind == "openai":
        _required(env, "HABLAIA_STT_BASE_URL", "HABLAIA_STT_API_KEY", "HABLAIA_STT_MODEL")
        base_url = env["HABLAIA_STT_BASE_URL"].strip()
        _https(base_url, "HABLAIA_STT_BASE_URL")
        return ProviderSpec(
            "openai",
            base_url=base_url,
            api_key=env["HABLAIA_STT_API_KEY"].strip(),
            model=env["HABLAIA_STT_MODEL"].strip(),
            language="es",
        )
    if kind == "azure":
        _required(env, "AZURE_SPEECH_KEY")
        region = env.get("AZURE_SPEECH_REGION", "westeurope").strip().lower()
        _azure_region(region)
        return ProviderSpec(
            "azure",
            api_key=env["AZURE_SPEECH_KEY"].strip(),
            region=region,
            language=env.get("AZURE_SPEECH_LANGUAGE", "es-ES").strip(),
        )
    raise ConfigError("HABLAIA_STT_PROVIDER must be mock, openai or azure")


def _llm(env: dict[str, str]) -> ProviderSpec:
    kind = env.get("HABLAIA_LLM_PROVIDER", "mock").strip().lower()
    if kind == "mock":
        return ProviderSpec("mock")
    if kind == "openai":
        _required(env, "HABLAIA_LLM_BASE_URL", "HABLAIA_LLM_API_KEY", "HABLAIA_LLM_MODEL")
        base_url = env["HABLAIA_LLM_BASE_URL"].strip()
        _https(base_url, "HABLAIA_LLM_BASE_URL")
        token_field = env.get("HABLAIA_LLM_TOKEN_FIELD", "max_tokens").strip()
        if token_field not in {"max_tokens", "max_completion_tokens"}:
            raise ConfigError("HABLAIA_LLM_TOKEN_FIELD must be max_tokens or max_completion_tokens")
        return ProviderSpec(
            "openai",
            base_url=base_url,
            api_key=env["HABLAIA_LLM_API_KEY"].strip(),
            model=env["HABLAIA_LLM_MODEL"].strip(),
            token_field=token_field,
        )
    raise ConfigError("HABLAIA_LLM_PROVIDER must be mock or openai")


def _tts(env: dict[str, str]) -> ProviderSpec:
    kind = env.get("HABLAIA_TTS_PROVIDER", "mock").strip().lower()
    if kind == "mock":
        return ProviderSpec("mock")
    if kind == "openai":
        _required(env, "HABLAIA_TTS_BASE_URL", "HABLAIA_TTS_API_KEY", "HABLAIA_TTS_MODEL", "HABLAIA_TTS_VOICE")
        base_url = env["HABLAIA_TTS_BASE_URL"].strip()
        _https(base_url, "HABLAIA_TTS_BASE_URL")
        return ProviderSpec(
            "openai",
            base_url=base_url,
            api_key=env["HABLAIA_TTS_API_KEY"].strip(),
            model=env["HABLAIA_TTS_MODEL"].strip(),
            voice=env["HABLAIA_TTS_VOICE"].strip(),
        )
    if kind == "azure":
        _required(env, "AZURE_SPEECH_KEY")
        region = env.get("AZURE_SPEECH_REGION", "westeurope").strip().lower()
        _azure_region(region)
        voice = env.get("AZURE_SPEECH_VOICE", "es-ES-ElviraNeural").strip()
        if not voice.replace(":", "").replace("-", "").isalnum():
            raise ConfigError("AZURE_SPEECH_VOICE has unexpected characters")
        return ProviderSpec(
            "azure",
            api_key=env["AZURE_SPEECH_KEY"].strip(),
            region=region,
            voice=voice,
            language=env.get("AZURE_SPEECH_LANGUAGE", "es-ES").strip(),
        )
    raise ConfigError("HABLAIA_TTS_PROVIDER must be mock, openai or azure")


def _https(url: str, name: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConfigError(f"{name} must be an https URL")


def _azure_region(region: str) -> None:
    if not region or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789" for char in region):
        raise ConfigError("AZURE_SPEECH_REGION must be a region id such as westeurope")
