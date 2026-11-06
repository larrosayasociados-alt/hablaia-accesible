# Contrato del futuro servidor

El dispositivo no lleva la persona ni la clave del servicio. Las guarda el servidor, fuera de git.

## Que hace el aparato al arrancar

Con la red ya conectada, `Ota::CheckVersion()` en `main/ota.cc` de xiaozhi-esp32 v2.5.2 hace lo siguiente:

1. Lee la clave NVS `ota_url` del espacio `wifi`. Si esta vacia, usa `CONFIG_OTA_URL`.
2. El valor por defecto de ese Kconfig, en el tag `v2.5.2`, es `https://api.tenclass.net/xiaozhi/ota/`.
3. Envia `POST` con cabeceras `Device-Id` (MAC Wi-Fi), `Client-Id` (UUID de la placa), `Accept-Language` (con `es-ES` si el perfil de este repositorio se compilo asi) y `User-Agent` `esp32-s3-touch-lcd-1.54/` mas la version de la aplicacion.
4. Guarda cada cadena del objeto JSON `websocket` en el espacio NVS `websocket`. Las claves que el protocolo lee despues son `url`, `token` y `version`.
5. Si la respuesta no trae `activation.code` ni `activation.challenge`, sigue sin pedir un codigo. Si trae `websocket` y no trae `mqtt`, abre el WebSocket. Si trae `mqtt`, elige MQTT.

La persona `asistente-senior` se aplica en ese servidor, al generar la respuesta de voz. No se compila en el ESP32.

## Como apuntar el aparato sin meter secretos en el repositorio

Hay dos sitios, y ninguno de los dos es un archivo de este repo:

- En el portal de aprovisionamiento. `WifiBoard` de v2.5.2 llama a `78/esp-wifi-connect` 3.3.1 con `show_ota_config = true`. El componente abre el portal en `http://192.168.4.1` y guarda la URL avanzada en NVS `wifi` / `ota_url`. El README del componente llama a ese campo Custom OTA URL.
- En un `sdkconfig` local, no versionado, cambiando `Default OTA URL` dentro del menu `Xiaozhi Assistant`. Ese archivo esta en `.gitignore`.

El token de `websocket.token` lo emite el servidor en cada respuesta y el dispositivo lo copia a NVS. Si el valor no contiene un espacio, el cliente le antepone `Bearer `. No hace falta, y no se debe, dejar un token de ejemplo relleno.

`config/backend/ota-response.example.json` usa el host reservado `voice.example.invalid`. El campo `firmware` lleva la version `2.5.2` y no lleva `url`, porque el cliente solo marca una actualizacion cuando `firmware.version` y `firmware.url` son cadenas. `server_time.timezone_offset` esta en minutos: el codigo suma `timezone_offset * 60 * 1000` milisegundos. 60 corresponde a CET; en horario de verano de Espana el valor es 120.

## Audio que el servidor debe esperar

En `main/protocols/websocket_protocol.cc` del tag fijado, el hello del dispositivo anuncia Opus, 16000 Hz, 1 canal y `OPUS_FRAME_DURATION_MS`. Ese macro vale 60 en `main/audio/audio_service.h`. La placa, en `config.h`, configura el codec de entrada y de salida a 24000 Hz. Si el hello del servidor trae un `sample_rate` distinto del de salida del codec, el firmware escribe un aviso de remuestreo. Para la voz hacia el altavoz, 24000 Hz coincide con `AUDIO_OUTPUT_SAMPLE_RATE`.

El documento `docs/websocket.md` del mismo tag describe el hello, las cabeceras y los tres formatos binarios. Hay que contrastarlo con el codigo antes de implementar el servidor.

## Identidad de placa y OTA oficial

`config.json` de la placa declara `type` y `name` `esp32-s3-touch-lcd-1.54`. Este perfil no crea otro tipo de placa. `docs/custom-board.md` advierte que cambiar la configuracion de una placa ya publicada es peligroso porque una OTA puede sustituir el firmware por el de esa misma identidad. Mientras `ota_url` siga vacia, el aparato pregunta al servidor por defecto de Xiaozhi y ese servidor puede ofrecer una imagen mas nueva para esta placa. Un servidor propio debe devolver la version que el aparato ya ejecuta, sin `firmware.url`, hasta que exista un canal de actualizacion propio. No se reutiliza el canal oficial para publicar una imagen de HablaIA.
