# Servidor de prueba

La guía completa, con la elección de Europa, las claves y el cambio de OTA en la placa, está en [docs/SERVIDOR.md](../docs/SERVIDOR.md).

Arranque en esta máquina, sin claves y sin salir a internet:

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m hablaia_server --check
HABLAIA_ALLOW_ANY_DEVICE=1 .venv/bin/python -m hablaia_server
```

Eso solo escucha en `127.0.0.1`. El reconocimiento, el modelo y la voz quedan en el sustituto local: no entienden lo que se dice. `HABLAIA_ALLOW_ANY_DEVICE` no vale cuando el proceso escucha en todas las interfaces.

Pruebas:

```bash
cd server
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Hace falta `libopus.so.0` (en Debian/Ubuntu, el paquete `libopus0`).
