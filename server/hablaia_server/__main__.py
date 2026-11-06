"""python -m hablaia_server [--check]

This process is a preview. It does not register a public name and it does not
talk to the production site.
"""

from __future__ import annotations

import logging
import sys

from aiohttp import web

from hablaia_server.app import create_app
from hablaia_server.audio import OpusError, opus_version
from hablaia_server.config import ConfigError, load_settings
from hablaia_server.logsafe import install
from hablaia_server.persona import PersonaError, load_persona


def main() -> int:
    install()
    try:
        settings = load_settings()
        persona = load_persona(settings.persona_path, settings.addendum_path)
        codec = opus_version()
    except (ConfigError, PersonaError, OpusError) as exc:
        print(f"hablaia-voice-preview: {exc}", file=sys.stderr)
        return 2
    if "--check" in sys.argv:
        print("mode=preview")
        print(f"opus={codec}")
        print(f"persona={persona.display_name} locale={persona.locale} sentences={persona.max_sentences}")
        print(f"stt={settings.stt.public_label()}")
        print(f"llm={settings.llm.public_label()}")
        print(f"tts={settings.tts.public_label()}")
        print("token_secret=" + ("ephemeral" if settings.ephemeral_secret else "set"))
        print(f"devices={len(settings.devices)} allow_any={str(settings.allow_any_device).lower()}")
        print(f"bind={settings.bind_host}:{settings.bind_port}")
        return 0
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("hablaia").info(
        "preview voice server starting. This is not a live deployment and it has no public production name."
    )
    if settings.ephemeral_secret:
        logging.getLogger("hablaia").warning(
            "HABLAIA_TOKEN_SECRET is unset. Tokens from this process die when it exits."
        )
    web.run_app(create_app(settings), host=settings.bind_host, port=settings.bind_port, print=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
