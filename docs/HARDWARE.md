# Hardware, copia de seguridad y compilacion

Este documento describe la unidad Waveshare que ya arranca con el firmware Xiaozhi de fabrica, la imagen oficial que la soporta y como volver a esa flash. No sustituye la copia que se esta leyendo en el Mac: esa lectura sigue en curso y este repositorio no la da por terminada.

## Placa

Producto: Waveshare ESP32-S3-Touch-LCD-1.54, SKU 33869 en la ficha de Waveshare. La variante sin tactil es otra placa (SKU 33867) y no es la de este perfil.

La ficha de Waveshare publica estas piezas:

- ESP32-S3R8, Xtensa LX7 de doble nucleo, hasta 240 MHz, Wi-Fi 2,4 GHz 802.11 b/g/n y Bluetooth 5 LE.
- 512 KB de SRAM, 384 KB de ROM, 8 MB de PSRAM apilada y 16 MB de Flash NOR externa.
- Pantalla de 1,54 pulgadas, 240 × 240, controlador ST7789 por SPI, color RGB565 en los ejemplos de Waveshare.
- Tactil CST816 por I2C. Solo la version Touch lleva este controlador.
- Microfono, altavoz, codec ES8311, ADC ES7210 para la captura y la cancelacion de eco, y amplificador NS4150B.
- IMU de seis ejes QMI8658.
- Ranura de tarjeta TF.
- USB Type-C, botones PLUS, PWR y BOOT, carga de bateria de litio de 3,7 V.

La lectura hecha en el Mac de Alejandro, y no repetida desde este repositorio, fue: ESP32-S3 revision v0.2, 8 MB de PSRAM embebida, flash QIO de 16 MB e interfaz USB-JTAG/serie. Encaja con el ESP32-S3R8 y la flash de 16 MB de la ficha. La copia de solo lectura de esa flash esta en el Mac y todavia no se considera completa.

## Lo que ya trae el cliente oficial

No hace falta escribir un firmware de placa nuevo para voz, pantalla, tactil, codec y Wi-Fi.

El soporte entro en el cliente `78/xiaozhi-esp32` con el pull request 1868 y esta en el release `v2.5.2` (commit `49b4380b3faa0ceadd28a3e78aaf0f311c46c57e`, 11 de octubre de 2026). El release publica el archivo `v2.5.2_waveshare-esp32-s3-touch-lcd-1.54.zip`, SHA-256 `35f745f502d3284823331fb3a091004ca74f8f3691c144e0a9969ea5bb714f9e`. Dentro va `merged-binary.bin`. Las notas del release dicen que se construyo con ESP-IDF 6.1.0 y que la compilacion no reemplaza una prueba en la placa.

El directorio de placa es `main/boards/waveshare/esp32-s3-touch-lcd-1.54`. Su `config.json` fija:

- `target`: `esp32s3`
- `type` y `builds[0].name`: `esp32-s3-touch-lcd-1.54`
- `sdkconfig_append`: `CONFIG_USE_WECHAT_MESSAGE_STYLE=n` y `CONFIG_USE_DEVICE_AEC=y`

`config.h` de ese directorio fija el hardware que el firmware usa:

| Funcion | Valor en v2.5.2 |
| --- | --- |
| Codec | ES8311 + ES7210, `BoxAudioCodec`, entrada y salida a 24000 Hz |
| I2S | MCLK GPIO8, BCLK GPIO9, WS GPIO10, DIN GPIO11, DOUT GPIO12, PA GPIO7 |
| I2C del codec y del tactil | SDA GPIO42, SCL GPIO41 |
| Pantalla | ST7789, 240×240, SPI modo 3 (`DISPLAY_SPI_MODE`), MOSI GPIO39, CLK GPIO38, CS GPIO21, DC GPIO45, RST GPIO40, backlight GPIO46 |
| Tactil | CST816, INT GPIO48, RST GPIO47, `scl_speed_hz` 100000 |
| Botones | PWR GPIO5, subir volumen GPIO4, bajar volumen GPIO0 |
| Bateria | enable GPIO2, ADC GPIO1, carga GPIO3 |

El release `v2.2.6` ya nombraba esta placa, pero arrancaba en bucle: `InitializeTouch()` fallaba con `invalid scl frequency` porque la configuracion I2C del CST816 dejaba la frecuencia a cero. En `v2.5.2` el mismo archivo asigna `tp_io_config.scl_speed_hz = 100000` antes de `esp_lcd_new_panel_io_i2c`. Este perfil fija `v2.5.2` por eso, no por ser la ultima confirmacion de `main`.

`main/CMakeLists.txt` de ese tag, en `CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54`, usa la fuente Noto Sans 20 (`font_noto_sans_basic_20_4`) y emoji de 64 px. El menu Kconfig se llama `Xiaozhi Assistant` y la entrada es `Waveshare ESP32-S3-Touch-LCD-1.54` (`BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54`). El prompt del choice en el codigo es `Target Board`. El README de la placa escribe el camino como `Xiaozhi Assistant -> Board Type -> Waveshare ESP32-S3-Touch-LCD-1.54`.

Los defaults del proyecto, no un parche de este repositorio, dejan la flash en 16 MB QIO y la tabla `partitions/v2/16m.csv`:

```
nvs,      data, nvs,     0x9000,    0x4000,
otadata,  data, ota,     0xd000,    0x2000,
phy_init, data, phy,     0xf000,    0x1000,
ota_0,    app,  ota_0,   0x20000,   0x3f0000,
ota_1,    app,  ota_1,   ,          0x3f0000,
assets,   data, spiffs,  0x800000,  8M,
```

`sdkconfig.defaults.esp32s3` activa `CONFIG_ESPTOOLPY_FLASHMODE_QIO`, `CONFIG_SPIRAM`, `CONFIG_SPIRAM_MODE_OCT`, `CONFIG_SPIRAM_SPEED_80M` y `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_240`. Tambien deja el modelo de palabra de activacion `CONFIG_SR_WN_WN9_NIHAOXIAOZHI_TTS`. El perfil HablaIA lo apaga en la linea de compilacion; no edita ese default.

### Lo que el cliente oficial no arranca

La ficha de la pantalla en Waveshare dibuja un ejemplo de temporizacion SPI modo 0. El `config.h` que realmente publica el cliente para esta placa fija `DISPLAY_SPI_MODE` en 3, y el `.cc` lo pasa a `spi_mode`. No se cambia.

El `.cc` de la placa inicializa alimentacion, I2C, SPI, ST7789, CST816, los tres botones, el codec y el temporizador de ahorro. No inicializa el QMI8658 ni la ranura TF. La propia guia XiaoZhi de Waveshare responde que el firmware funciona sin tarjeta TF y que no lee archivos de esa tarjeta. Una funcion posterior de caidas o de registro en la tarjeta si necesitaria codigo de placa. La voz en espanol no lo necesita.

La serigrafia de Waveshare nombra PLUS, PWR y BOOT. El firmware asigna GPIO0, que es la patilla BOOT del ESP32-S3, a bajar volumen; GPIO4 a subir volumen; GPIO5 a encendido. Este repositorio no ha medido PLUS contra el esquema mas alla de esas asignaciones.

En el codigo de la placa, el boton de encendido hace esto:

- pulsacion corta: alterna la conversacion (`ToggleChatState`)
- pulsacion larga: apaga
- doble pulsacion: apaga o recupera el backlight
- tres pulsaciones: entra en el modo de configuracion Wi-Fi

Subir y bajar volumen cambian el nivel de 10 en 10. Una doble pulsacion de bajar volumen, con el dispositivo en reposo, conmuta el AEC de la placa. `CONFIG_USE_DEVICE_AEC` ya viene activado en el `config.json` de esta placa.

## Idioma y herramientas

El Kconfig `Default Language` incluye `LANGUAGE_ES_ES` (`Spanish`). Existe `main/assets/locales/es-ES/language.json` con los textos de pantalla, entre ellos `LISTENING` = `Escuchando...`, `SPEAKING` = `Hablando...` y `WIFI_CONFIG_MODE` = `Modo configuración de red`, y los avisos de voz `.ogg` de ese directorio. `scripts/build.py` acepta `--language es-ES`.

El README del cliente en el tag `v2.5.2` dice:

- el minimo es ESP-IDF v6.0.1
- la rama recomendada es `release/v6.1`, no la etiqueta `v6.1` (el README cita el fallo de Wi-Fi en ESP32-C3 del issue 2344)
- ESP-IDF 5.x ya no esta soportado por este cliente
- despues de cambiar de revision del SDK hay que ejecutar `git submodule update --init --recursive` dentro del directorio de ESP-IDF, cargar `export.sh` y ejecutar `idf.py fullclean` en el proyecto

La imagen de `docker/firmware-builder/Dockerfile` usa por defecto `espressif/idf:release-v6.1`. Las notas de `v2.5.2` dicen que la matriz se construyo con ESP-IDF 6.1.0.

La pagina de Waveshare "Working with ESP-IDF" para esta placa pide ESP-IDF V5.5.0 o superior y ensena capturas de V5.5.2. Esa pagina es para los ejemplos de Waveshare, no para xiaozhi-esp32 `v2.5.2`. Compilar este cliente con 5.5 contradice el README del cliente.

## Comandos de compilacion

En este entorno no esta instalado ESP-IDF y no se ha flasheado. Sobre un checkout del tag se ejecuto `python3 scripts/build.py --list-languages` y la salida incluye `es-ES`. `--list-boards` lee la version del SDK en `tools/cmake/version.cmake`; para ese listado se le dio solo ese archivo con 6.1.0, la version que las notas del release dicen haber usado, mas las fuentes de `main/boards`. El JSON de esa placa es una sola variante: directorio `waveshare/esp32-s3-touch-lcd-1.54`, nombre `esp32-s3-touch-lcd-1.54`, nombre completo `waveshare-esp32-s3-touch-lcd-1.54`, Kconfig `CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54` y AEC de dispositivo por defecto. No se ejecuto `idf.py build`.

Salen de los documentos del tag, no de una receta nueva. Este repositorio no los ejecuta contra una placa y no flashea.

Preparacion del SDK, como indica el README del cliente:

```bash
git submodule update --init --recursive
. ./export.sh
```

El `export.sh` es el de ESP-IDF. El README pide la rama `release/v6.1`.

Camino del README de la placa (`main/boards/waveshare/esp32-s3-touch-lcd-1.54/README.md`):

```bash
git clone https://github.com/78/xiaozhi-esp32.git
cd xiaozhi-esp32
idf.py set-target esp32s3
idf.py menuconfig
```

En menuconfig: `Xiaozhi Assistant`, despues el tipo de placa `Waveshare ESP32-S3-Touch-LCD-1.54`, y el idioma `Spanish`. El README de la placa sigue con:

```bash
idf.py build
```

y, en el mismo archivo, `idf.py build flash monitor`. Ese segundo comando escribe la flash. No se usa hasta que la copia del Mac este terminada y comprobada, y solo en el ordenador que tiene el cable.

Camino que `docs/custom-board.md` llama opcion recomendada cuando hay `config.json`. Para esta placa, el directorio relativo a `main/boards` y el `builds[].name` son:

```bash
python scripts/build.py waveshare/esp32-s3-touch-lcd-1.54 \
  --name esp32-s3-touch-lcd-1.54 \
  --language es-ES \
  --wake-word disabled
```

`--wake-word disabled` esta documentado en ese archivo y en la ayuda de `scripts/build.py`. Tambien lo acepta el patron del constructor Docker (`disabled`, `nihaoxiaozhi` o `wn9...`). Sin esa opcion, `sdkconfig.defaults.esp32s3` deja la palabra china `nihaoxiaozhi`. Con ella, la conversacion arranca con la pulsacion corta del boton de encendido. No hay en la ayuda de `build.py` un modelo de palabra de activacion en espanol; no se inventa uno aqui.

El constructor publicado en `docker/firmware-builder/README.md` recibe las mismas decisiones por entorno: `FIRMWARE_BOARD_DIR`, `FIRMWARE_BOARD_NAME`, `FIRMWARE_LANGUAGE` y `FIRMWARE_WAKE_WORD`. La imagen de produccion de ese documento esta pensada para `linux/arm64`. No se construye ni se publica desde aqui.

`python scripts/build.py` genera `build/merged-binary.bin` y no crea el ZIP salvo que se pase `--zip`. No anade un paso de flasheo.

Comprobar valores admitidos, tambien segun `docs/custom-board.md`:

```bash
python scripts/build.py --list-languages
python scripts/build.py --list-boards
```

`--list-wake-words` lee el componente ESP-SR ya resuelto. El propio documento dice que antes hace falta `idf.py reconfigure` si `managed_components/` aun no existe.

## Copia de seguridad y vuelta al firmware de origen

Hay tres imagenes distintas y no se pueden usar unas por otras:

1. La flash que ahora mismo tiene la unidad. Es la unica copia bit a bit del firmware chino que ya se conecta por Wi-Fi, incluidas las credenciales de la NVS. Se esta leyendo en el Mac. Este repositorio no tiene ese archivo, no conoce su tamano final ni su SHA-256, y no afirma que la lectura haya acabado.
2. El ZIP oficial `v2.5.2_waveshare-esp32-s3-touch-lcd-1.54.zip`. Es una imagen Xiaozhi conocida para esta placa, en chino por defecto y apuntando al servidor por defecto. No es la flash actual de la unidad.
3. Una compilacion futura con `--language es-ES`. Sustituye la aplicacion. No restaura la unidad.

Hasta que el archivo del Mac exista, tenga el tamano de la flash detectada y este copiado fuera de la placa, no se borra ni se escribe la flash.

Lectura, tomada de la documentacion de esptool (`read-flash`). El ejemplo oficial usa 460800 baudios y `ALL` para detectar el tamano. En el Mac se sustituye `PORT` por el dispositivo USB que ya esta usando la lectura en curso:

```bash
esptool -p PORT -b 460800 read-flash 0 ALL flash_contents.bin
```

`ALL` es el modo documentado para no quedarse cortos si la herramienta ve 16 MB. Una flash de 16 MB son 16777216 bytes. Si el archivo aun esta creciendo, o pesa menos que el tamano que esptool anuncio, la copia no esta completa. Despues de cerrarla, se calcula el SHA-256 y se guarda junto al binario, fuera de git. `.gitignore` excluye `*.bin`, `backups/` y `secrets/`. La NVS de esta tabla empieza en `0x9000` y contiene el Wi-Fi; el archivo es un secreto.

La misma pagina de esptool documenta el borrado total:

```bash
esptool erase-flash
```

Eso sustituye toda la flash por `0xFF`. No se usa como preparacion de esta placa.

Para devolver la unidad a la lectura completa, `write-flash` escribe en la direccion `0` el archivo leido. La documentacion de esptool muestra la forma general `write-flash` con direccion y archivo, y advierte que un binario fusionado rellena los huecos con `0xFF` y, al escribirlo, borra los sectores de esos huecos. Por eso el ZIP oficial no conserva el Wi-Fi de la unidad: la via de retorno del estado actual es el `read-flash` completo, no el ZIP.

Waveshare, en "Firmware Flashing and Erasing", flashea el binario de sus ejemplos en la direccion `0x00` con Espressif Flash Download Tool, baudios 1152000, y el boton ERASE borra la flash entera. Si la herramienta se queda en "Waiting for power-on sync", hay que mantener BOOT y quitar y poner la alimentacion. Esas instrucciones son las del binario de demostracion de Waveshare. En el Mac, la via publicada para la imagen Xiaozhi es esptool o `idf.py`, no esa herramienta de Windows.

El issue 2003 del cliente muestra una escritura real de un `merged-binary.bin` de esta placa en el offset `0x0`. Sirve como precedente del offset, no como orden para ejecutarla ahora.

`idf.py build flash monitor`, que es la linea del README de la placa, tambien escribe la flash. Queda para el Mac, despues de la copia, y no forma parte de la CI.

Restaurar el ZIP oficial devuelve una aplicacion Xiaozhi de esta placa, en el idioma por defecto del release, y puede borrar la NVS. Restaurar el `read-flash` del Mac devuelve el firmware con el que la unidad ya habla por Wi-Fi, credenciales incluidas. Son recuperaciones distintas. Las dos siguen siendo posibles porque este perfil no cambia la tabla de particiones ni el tipo de placa.

## Que no se ha hecho desde aqui

No se ha flasheado, no se ha abierto el puerto USB de la unidad y no se ha contactado ningun servicio de produccion. La compilacion del firmware exige ESP-IDF `release/v6.1` y el gestor de componentes; este entorno no trae ese SDK. La CI comprueba el pin, los hashes de los archivos citados y que el perfil en espanol sea coherente. No genera `merged-binary.bin`.
