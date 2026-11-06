# Arquitectura del prototipo

Se puede usar el cliente oficial Xiaozhi en esta placa sin escribir firmware de placa. El prototipo en espanol es una seleccion de compilacion y una persona de servidor. El codigo que enciende la pantalla, el tactil, el codec y los botones permanece en `78/xiaozhi-esp32` tag `v2.5.2`.

## Que va en el dispositivo y que no

El firmware oficial ya sabe hacer de esta placa un cliente de voz:

- Se conecta a Wi-Fi. Si no hay red guardada, abre el punto de acceso `Xiaozhi-` y el portal `http://192.168.4.1` (`78/esp-wifi-connect` 3.3.1, con la pestaña avanzada visible porque `WifiBoard` pone `show_ota_config = true`).
- Habla con un servidor por el protocolo WebSocket descrito en `docs/websocket.md` del tag, o por MQTT+UDP si la respuesta OTA trae `mqtt`.
- Muestra los textos de `main/assets/locales/es-ES` cuando se compila con `--language es-ES`.
- Reproduce los avisos de voz de esa carpeta. La voz del modelo no sale del ESP32: la sintetiza el servidor.

La persona `Asistente senior` esta en `config/persona/asistente-senior.es.json` y el campo `applies_on` es `server`. El modelo de lenguaje no lee ese archivo desde la flash. Cuando exista el servidor de HablaIA, ese proceso carga el archivo, o una copia publicada aparte, y lo usa como instruccion de sistema. Cambiar el tono no exige recompilar la placa.

El dispositivo no debe llevar tokens, contrasenas de Wi-Fi ni la URL privada del servidor dentro del git. Esos valores viven en la NVS de la unidad o en el entorno del servidor. El detalle del JSON de arranque esta en `config/backend/README.md`.

## Camino hasta un servidor propio

```text
pulsacion corta de encendido
        |
        v
cliente Xiaozhi v2.5.2  --POST-->  URL NVS wifi/ota_url
lenguaje es-ES                     o CONFIG_OTA_URL si la NVS esta vacia
        |
        v
respuesta JSON websocket.url + token emitido en ese momento
        |
        v
WebSocket  Opus 16000 Hz / 60 ms hacia el servidor
           Opus de vuelta, a ser posible 24000 Hz
        |
        v
el servidor aplica asistente-senior y devuelve audio
```

Mientras la clave `ota_url` este vacia, el aparato sigue el valor por defecto del Kconfig, `https://api.tenclass.net/xiaozhi/ota/`, y la persona del prototipo no interviene. Eso permite probar la interfaz en espanol contra el servicio que la unidad ya conoce, y tambien permite que ese servicio ofrezca una OTA para la identidad `esp32-s3-touch-lcd-1.54`.

Cuando se quiera el servidor de HablaIA:

1. Se publica un endpoint OTA de prueba, no un host de produccion, que responda como `config/backend/ota-response.example.json`: objeto `websocket`, sin objeto `mqtt`, version de firmware igual a la que corre el aparato y sin `firmware.url`.
2. En el portal de la placa, pestaña avanzada, se escribe esa URL. Queda en la NVS. No se copia al repositorio. Un archivo local `ota-url.local` esta ignorado por git por si hace falta anotarla en el Mac.
3. El servidor guarda el token por `Device-Id` y lo devuelve en `websocket.token`. El cliente lo manda como `Authorization`.
4. El mismo servidor elige la persona `asistente-senior` para ese dispositivo.

No se crea un `BOARD_TYPE` nuevo. `docs/custom-board.md` del cliente explica que cada placa publicada tiene su canal de actualizacion y que pisar esa identidad hace que una OTA oficial pueda reemplazar el firmware. Mantener `esp32-s3-touch-lcd-1.54` es la compatibilidad con el ZIP oficial y con la flash de fabrica. El aislamiento respecto del servidor oficial es la URL de la NVS, no un fork de la placa.

## Limites conscientes del primer prototipo

- La palabra de activacion por defecto del ESP32-S3 en este tag es el modelo chino `nihaoxiaozhi`. El perfil la desactiva. La persona mayor pulsa el boton de encendido. Un modelo de activacion en espanol no esta en la lista que documenta `build.py`; el generador de recursos del proyecto (`78/xiaozhi-assets-generator`, citado en el README del cliente) es el sitio donde eso se haria mas adelante.
- El IMU QMI8658 y la tarjeta TF no estan inicializados. No forman parte de este prototipo de voz.
- El cliente necesita red. La guia de Waveshare lo dice para XiaoZhi y el codigo no trae un modelo de lenguaje en la placa.
- La pantalla y los avisos fijos salen en espanol. La respuesta libre sale en espanol solo si el servidor usa la persona y un TTS `es-ES`. El servidor oficial no tiene por que hacerlo.

## Qué ya está en el firmware y qué espera un servidor

En la imagen de esta rama, sin un servidor HablaIA:

- Pantalla, táctil, codec, AEC, botones y Wi-Fi del cliente oficial.
- Textos y avisos fijos en `es-ES`. La palabra de activación china queda desactivada en el perfil de compilación. La pulsación corta de encendido abre la conversación.
- El aviso de movimiento: a las 09:00, 12:00, 15:00 y 18:00 hora de Madrid, una frase corta en pantalla y en un Opus grabado en el aparato. Descartar, aplazar y no repetir el mismo turno están en `firmware/movement_reminder/` y tienen pruebas que no necesitan la placa.
- El reloj se acepta cuando la respuesta OTA trae `server_time`. El desfase que Xiaozhi suma al reloj se guarda y se deshace para calcular Madrid. Eso puede seguir haciéndolo el servidor Xiaozhi por defecto. El aviso de cada tres horas no necesita un servidor HablaIA.

La conversación libre sí lo necesita. El botón de hablar abre el canal de voz contra la URL que devuelva la OTA. La persona Asistente senior, el modelo y la voz de esa conversación no están en la flash. Un servidor posterior puede además mandar un mensaje `notify`, como describe `docs/notify.md` del tag; el aviso horario no depende de ese mensaje.

## Qué queda fuera de este repositorio

No hay implementación del servidor, no hay despliegue y no hay cambios en recursos que ya estén en producción. La vuelta al programa original es la copia de 16 MB del Mac, descrita en `docs/PRUEBA.md`. El ZIP oficial de esta misma placa es otra imagen, no esa copia.
