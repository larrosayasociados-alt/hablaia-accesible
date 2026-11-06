# Servidor de voz de prueba

Este proceso habla el protocolo del cliente [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) `v2.5.2`, commit `49b4380b3faa0ceadd28a3e78aaf0f311c46c57e`. La ficha está en `config/protocol-pin.json`. El código que se ha contrastado es `docs/websocket.md`, `main/protocols/websocket_protocol.cc`, `main/protocols/protocol.h`, `main/protocols/protocol.cc`, `main/ota.cc` y `main/audio/audio_service.h` de ese commit.

No está desplegado. No tiene un nombre público. Las pruebas automaticas cubren el protocolo en este ordenador. No demuestran que la placa ya haya conversado con este servidor.

El otro cambio del repositorio, el del firmware, no se modifica desde aquí. Tampoco se flashea la placa ni se toca el sitio que ya está publicado.

## Qué hace el aparato

Con la red ya unida, `Ota::CheckVersion()` envía `POST` a la URL NVS `wifi/ota_url`. Si esa clave está vacía, usa `https://api.tenclass.net/xiaozhi/ota/`.

La respuesta de este servidor lleva tres objetos y nada más:

- `firmware.version`, copiada de `application.version` si viene bien formada. No lleva `firmware.url`. En `ota.cc`, el cliente solo marca una actualización cuando `version` y `url` son las dos cadenas.
- `server_time`, descrito más abajo.
- `websocket.url`, `websocket.token` y `websocket.version` = `1`. No hay objeto `mqtt`. Si la respuesta trajera los dos, el cliente `v2.5.2` se quedaría con MQTT.

El token no contiene espacios. El cliente, en `websocket_protocol.cc`, le antepone `Bearer ` y abre `websocket.url` con las cabeceras `Authorization`, `Protocol-Version`, `Device-Id` y `Client-Id`.

Después manda un JSON `type: hello` con `transport: websocket` y Opus de subida a 16000 Hz, mono, tramas de 60 ms (`OPUS_FRAME_DURATION_MS`). Espera menos de 10 segundos un hello de vuelta con `transport: websocket`. Este servidor contesta con Opus de bajada a 24000 Hz y 60 ms, que es la salida del codec de la placa `esp32-s3-touch-lcd-1.54` en ese tag. Si la cifra no coincide, `application.cc` avisa de que va a remuestrear.

La versión binaria por defecto del cliente es la 1: cada trama Opus va en un frame binario, sin cabecera. Las versiones 2 y 3 de `protocol.h` también se aceptan si el aparato manda `Protocol-Version`. La OTA de este servidor pide siempre la versión 1.

El botón de encendido, con el AEC de servidor apagado, usa el modo `auto` (`Application::GetDefaultListeningMode`). En ese modo el aparato no manda `listen stop` al terminar la frase: envía Opus hasta que el servidor dice `tts start`. Este servidor cierra el turno cuando, tras un poco de voz, llegan unas tramas en silencio. El modo `manual` sigue aceptando `listen stop`.

El orden hacia el aparato es el que `application.cc` puede pintar y oír:

1. `stt` con el texto.
2. `llm` con emoción `neutral`.
3. `tts` `start`, que pasa el aparato a «hablando». Hasta ese momento tira el audio.
4. `tts` `sentence_start` con la frase, para la pantalla de 240 por 240.
5. Una pausa corta, porque `tts start` se aplica en el bucle principal y un Opus inmediato se pierde.
6. Tramas Opus, más o menos una cada 60 ms, para no llenar la cola de 20 paquetes.
7. `tts` `stop`.

Un mensaje `mcp` se registra y no se ejecuta. Este servidor no anuncia herramientas. No manda `system reboot`.

## Reloj y `timezone_offset`

`main/ota.cc` hace esto con `server_time`:

```text
timestamp_ms += timezone_offset * 60 * 1000
settimeofday(timestamp_ms / 1000)
```

`timestamp` son milisegundos UTC. `timezone_offset` son minutos al este de UTC. El parche del firmware guarda ese entero en NVS `hablaia/ota_tz_min` y el aviso de movimiento lo deshace antes de calcular Madrid:

```text
utc = device_unix - ota_offset_minutes * 60
```

Este servidor manda el desfase de `Europe/Madrid`, no una hora ya desplazada. En invierno son 60 minutos (CET). En horario de verano son 120 (CEST). La regla es la del firmware: el horario de verano va desde el último domingo de marzo a las 01:00 UTC hasta el último domingo de octubre a las 01:00 UTC, sin incluir ese instante. Así el reloj de la placa lee la hora de España, y al restar el mismo entero el aviso de las 09:00, 12:00, 15:00 y 18:00 sigue cayendo en Madrid aunque otro servidor hubiera mandado otro desfase.

## Por qué no va en un Worker

HablaIA ya usa Cloudflare para la web. Un Worker normal no es el sitio de esta sesión. La documentación actual de Workers dice que, en una actualización del runtime, las conexiones abiertas —incluidos los WebSocket— tienen como mucho unos 20 minutos para terminar y después el proceso las corta. Lo mismo vale para un WebSocket que siga abierto durante esa ventana. Fuente: [Limits](https://developers.cloudflare.com/workers/platform/limits/), apartado de actualizaciones del runtime y de tiempo de CPU.

Los Durable Objects sí documentan WebSocket, con la API de hibernación: la conexión puede seguir mientras el objeto duerme, y al llegar un mensaje el objeto se vuelve a crear y pierde la memoria. Fuente: [Use WebSockets](https://developers.cloudflare.com/durable-objects/best-practices/websockets/). Hibernar entre medias borra el buffer de Opus, el estado del descodificador y la detección de silencio. Mientras llega una trama cada 60 ms el objeto no duerme. Un WebSocket de salida, el que haría falta para un reconocimiento en streaming, no hiberna, y uno abierto solo evita el desalojo unos 15 minutos. El límite de CPU por invocación sigue en 30 segundos por defecto (hasta 5 minutos en el plan de pago) y hay 6 conexiones de salida simultáneas por petición. Fuentes: la misma página de WebSockets y [Durable Object limits](https://developers.cloudflare.com/durable-objects/platform/limits/).

Además, el descodificador que usa el cliente es Opus, y aquí se enlaza `libopus` 1.4. Eso es un proceso con una librería nativa, no el aislado de Workers.

Por eso el preview es un proceso Python que se queda escuchando. No es un Worker.

## Dónde puede vivir en Europa

Hace falta una máquina que acepte un WebSocket en los dos sentidos y no lo corte por estar un rato en silencio.

La opción escrita en `server/fly.toml` es una Machine de Fly.io en `fra` (Fráncfort). Fly documenta esa región en [Regions](https://docs.fly.io/reference/regions) y dice que el proxy reenvía `ws://` y `wss://` sin un módulo aparte, y que no cierra un WebSocket solo porque no haya tráfico. Sí lo cierra si la máquina se para por autostop, si hay un despliegue o si reinicia el proxy. Fuente: [WebSockets](https://docs.fly.io/networking/websockets). El toml deja `auto_stop_machines = "off"` y una sola máquina pequeña para que el proxy no corte el audio por parar el proceso. No tiene nombre de host. No apunta al sitio público.

Precios que la tabla de [fly.io/pricing](https://fly.io/pricing) publicaba al revisar esto, para 30 días encendida, en Fráncfort (multiplicador 1,154 sobre Ashburn, aplicado a vCPU y RAM): `shared-cpu-1x` con 256 MB, 2,53 USD; `performance-1x` con 2 GB, 38,08 USD. Se factura por segundo mientras la máquina corre. Puede cambiar. No se ha creado ninguna aplicación ni se ha encendido esa facturación.

La otra opción, sin cifra porque no se ha consultado una tarifa, es una máquina virtual en un centro de Hetzner en Europa. La documentación de Hetzner lista Falkenstein (`fsn1`), Núremberg (`nbg1`) y Helsinki (`hel1`) en la zona `eu-central`. Fuente: [Locations](https://docs.hetzner.com/cloud/general/locations/). `deploy/hablaia-voice-preview.service` es un ejemplo de systemd para esa máquina. No está instalado en ningún sitio.

En los dos casos el proceso es el mismo contenedor o el mismo `python -m hablaia_server`. El TLS lo pone el proxy o un reverse proxy delante. El aparato, fuera de casa, necesita `wss://`.

No se despliega nada hasta que Alejandro apruebe un nombre de preview y el gasto. Ese nombre no es el dominio público de producción.

## Arranque local

Hace falta Python 3.12 y `libopus.so.0` (paquete `libopus0` en Debian/Ubuntu). Esta revisión lo ha ejecutado con libopus 1.4.

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m hablaia_server --check
```

`--check` imprime el modo `preview`, la versión de Opus, la persona y si cada etapa es `mock` o un proveedor. No imprime claves.

Para escuchar solo en esta máquina, con cualquier MAC y sin claves:

```bash
HABLAIA_ALLOW_ANY_DEVICE=1 .venv/bin/python -m hablaia_server
```

Queda en `http://127.0.0.1:8787`. `GET /health` responde `{"status":"ok","mode":"preview"}`. `POST /xiaozhi/ota/` y el WebSocket están en `/xiaozhi/v1/`.

`HABLAIA_ALLOW_ANY_DEVICE` se rechaza si `HABLAIA_BIND` es `0.0.0.0`. En un ordenador de prueba que no está expuesto, la lista vacía también se puede abrir con un dispositivo concreto:

```bash
export HABLAIA_TOKEN_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export HABLAIA_DEVICES="aa:bb:cc:dd:ee:ff"
.venv/bin/python -m hablaia_server
```

La MAC es la de la cabecera `Device-Id`, la del Wi-Fi, en la forma `aa:bb:cc:dd:ee:ff`. El secreto y la MAC no se escriben en git. Si falta `HABLAIA_TOKEN_SECRET`, el proceso inventa uno y los tokens mueren al salir. El registro avisa de eso y no imprime el secreto.

Sin `HABLAIA_DEVICES` y sin `HABLAIA_ALLOW_ANY_DEVICE`, la OTA responde 403 a todo el mundo y no devuelve token.

La imagen, cuando haya Docker, se construye desde la raíz del repositorio. Aquí no había Docker, así que esa imagen no se ha construido:

```bash
docker build -f server/Dockerfile -t hablaia-voice-preview .
```

Dentro del contenedor hay que poner `HABLAIA_BIND=0.0.0.0:8787`, la URL pública `wss://…/xiaozhi/v1/`, el secreto y la lista de MAC. Si falta la URL pública, el proceso no arranca: no va a anunciar `0.0.0.0` a la placa.

## Claves y servicios

Cada etapa se elige sola. El valor por defecto de las tres es `mock`: no llama a nadie, no reconoce español y contesta una frase fija que dice que esto es una prueba. Sirve para ver el protocolo. No sirve para hablar con una persona.

| Variable | Valores | Para qué |
| --- | --- | --- |
| `HABLAIA_STT_PROVIDER` | `mock`, `openai`, `azure` | Reconocimiento |
| `HABLAIA_LLM_PROVIDER` | `mock`, `openai` | Modelo. `openai` significa la API de chat completions, no una empresa concreta |
| `HABLAIA_TTS_PROVIDER` | `mock`, `openai`, `azure` | Voz |
| `HABLAIA_LLM_BASE_URL` | URL `https` | Por ejemplo `https://api.eu.mistral.ai/v1` |
| `HABLAIA_LLM_API_KEY` | clave | No va en el código |
| `HABLAIA_LLM_MODEL` | id del modelo | Tiene que existir en ese endpoint |
| `HABLAIA_LLM_TOKEN_FIELD` | `max_tokens` o `max_completion_tokens` | Mistral usa `max_tokens` |
| `HABLAIA_STT_BASE_URL`, `HABLAIA_STT_API_KEY`, `HABLAIA_STT_MODEL` | | `POST /audio/transcriptions` con `language=es` |
| `HABLAIA_TTS_BASE_URL`, `HABLAIA_TTS_API_KEY`, `HABLAIA_TTS_MODEL`, `HABLAIA_TTS_VOICE` | | `POST /audio/speech`, WAV |
| `AZURE_SPEECH_KEY` | clave del recurso | STT y TTS |
| `AZURE_SPEECH_REGION` | `westeurope` por defecto | También vale otro id de región, en minúsculas |
| `AZURE_SPEECH_LANGUAGE` | `es-ES` | |
| `AZURE_SPEECH_VOICE` | `es-ES-ElviraNeural` | Otra voz `es-ES` de la lista de Microsoft |

La plantilla vacía está en `server/.env.example`.

Combinación pensada para Europa, a confirmar con las cuentas antes de usarla:

- Modelo: Mistral en el endpoint regional `https://api.eu.mistral.ai/v1`. La documentación dice que esa inferencia se procesa en centros de la UE y la AELC, que no fija la ubicación del plano de control, y que se factura a 1,1 veces la tarifa de lista. Fuente: [Regional inference](https://docs.mistral.ai/inference/regional-inference). El id del modelo hay que tomarlo de la lista de ese endpoint. No se deja uno fijo aquí porque esa lista cambia.
- Reconocimiento y voz: Azure Speech en `westeurope`, que la tabla de regiones de Microsoft marca como región europea con STT y TTS. El reconocimiento corto usa `language=es-ES`. La voz por defecto es `es-ES-ElviraNeural`, voz neuronal de español de España, con ritmo `slow`. Fuentes: [regiones](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions), [idiomas y voces](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt), [STT corto](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-speech-to-text-short) y [TTS REST](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech), que lista `https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1`. No se copia aquí un precio de Azure: no se ha consultado.

El reconocimiento corto de Azure admite como máximo unos 60 segundos por petición. El servidor no acumula más de eso.

La persona que recibe el modelo es `config/persona/asistente-senior.es.json`, la misma ficha de servidor del firmware (`applies_on: server`, español de España, usted, tres frases como máximo). Se le añade `config/persona/server-addendum.es.txt`: no pedir ni repetir tarjetas, cuentas, claves ni datos de salud; no dar consejos médicos; no describir llamadas, mensajes, banco, correo ni citas, porque el aparato no los hace. El servidor corta la respuesta a tres frases y tapa secuencias largas de dígitos antes de decirlas o de guardarlas en la memoria breve del proceso. Esa memoria no se escribe en disco y no se usa con el modelo simulado.

Una voz de la API compatible con OpenAI no garantiza acento de España. Para eso está la voz neuronal `es-ES` de Azure. El endpoint global de un proveedor que no documente la región no cuenta como tratamiento en Europa.

## Cómo apuntar la placa, y cómo volver a Xiaozhi

Esto no se ha hecho. La placa sigue con su servidor hasta que alguien escriba otra URL en la NVS.

La URL de prueba es la de la OTA de este proceso, no la del WebSocket. El aparato la pide y, en la respuesta, recibe el WebSocket y el token. Un ejemplo de forma, sin token y sin host real, está en `config/backend/ota-response.example.json`. El proceso rellena el timestamp, el desfase y el token. El host `voice.example.invalid` de ese archivo no se usa.

En la placa Waveshare de este tag, tres pulsaciones seguidas del botón de encendido llaman a `EnterWifiConfigMode()` (`esp32-s3-touch-lcd-1.54.cc`). Se abre el punto de acceso y el portal `http://192.168.4.1`. El componente `esp-wifi-connect` 3.3.1, con la pestaña avanzada visible, guarda el campo Custom OTA URL en NVS `wifi` / `ota_url`. Ahí iría la URL de prueba, por ejemplo `http://192.168.1.20:8787/xiaozhi/ota/` en la red de casa, o un `https://…/xiaozhi/ota/` el día que exista un preview aprobado. No se copia al repositorio. Un archivo `ota-url.local` está ignorado por git.

Para volver al servicio Xiaozhi:

1. Abrir otra vez el portal (las tres pulsaciones).
2. Vaciar Custom OTA URL y guardar.
3. Reiniciar. Con la clave vacía, `GetCheckVersionUrl()` usa `https://api.tenclass.net/xiaozhi/ota/`.
4. Una respuesta correcta de ese servicio vuelve a escribir en la NVS la URL y el token de WebSocket. Hasta que esa petición tiene éxito, el aparato puede seguir usando el WebSocket que guardó la última OTA.

No hace falta borrar la flash para ese cambio de servidor. La copia de 16 MB del aparato, y cómo restaurarla, siguen documentadas en el cambio de firmware. Este repositorio no contiene esa copia.

## Pruebas

```bash
cd server
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Cubren:

- el desfase de Madrid en invierno, en verano y en los dos cambios de hora, igual que `Europe/Madrid`, y la cuenta que hace el firmware al sumar y luego restar el offset;
- OTA con URL, token, versión de firmware sin `url`, sin `mqtt`, y 403 sin token si la MAC no está;
- el WebSocket rechaza un token ausente, caducado o de otro aparato;
- hello, `stt`, `llm`, `tts` y tramas Opus que `libopus` descodifica;
- el modo `auto` cierra el turno al quedar la señal en silencio, sin `listen stop`;
- la versión binaria 2;
- el registro de ese turno no contiene el token, el secreto, el Opus en hexadecimal ni un número de serie de prueba.

`python -m hablaia_server --check` comprueba que el proceso carga la persona y Opus.

## Registro

En el nivel INFO se anota el tipo de mensaje, la MAC, cuántas tramas y cuántos bytes, el código de un fallo del proveedor y el desfase horario. No se escribe el audio, el token, la cabecera `Authorization`, las claves ni el número de serie. Un filtro aparte tapa un `Bearer` o un token `v1.` si alguna línea los llegara a incluir. El texto reconocido y la respuesta no se registran.

## Qué no hace todavía

- Nadie ha apuntado la placa a este proceso. Una prueba verde no es una conversación oída en el altavoz.
- Sin las claves, el servidor no entiende lo que se dice. La frase de prueba lo dice.
- La detección de fin de frase en modo `auto` es un umbral de energía, no un modelo de voz. Puede cortar pronto, esperar de más, o volver a contestar si el micrófono oye al altavoz. Tras cada respuesta se ignoran unas tramas, y eso no sustituye a un AEC ajustado.
- El modo `realtime` se trata como `auto`. No hay cancelación de eco en el servidor.
- La respuesta se dice cuando el modelo ha terminado la frase, no palabra a palabra.
- El reconocimiento real, cuando se configura Azure, es una petición por turno, no un stream parcial. El tope documentado de ese API corto es de unos 60 segundos.
- No hay herramientas MCP, ni avisos `notify`, ni canal de actualización de firmware. El aviso de movimiento sigue viviendo en la placa.
- La memoria del diálogo se borra al salir el proceso.
- El cliente cierra el canal si pasa unos 120 segundos sin recibir nada (`Protocol::IsTimeout` en `protocol.cc`). Un ping de WebSocket no cuenta como mensaje de ese protocolo.
- Este árbol no crea la máquina en Fráncfort ni en Hetzner, no pide certificados y no enciende facturación.
