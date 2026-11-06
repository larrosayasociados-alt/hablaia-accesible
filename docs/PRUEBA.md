# Primera instalación de prueba

Esta prueba se hace en el Mac, con el cable, después de compilar. Desde este repositorio no se flashea. El archivo de 16 MB de la flash original no se copia aquí: contiene el Wi-Fi y otros datos de la NVS.

La copia que ya terminó mide 16777216 bytes y su SHA-256 es `037b8878a1ad0e344ffc88eb7f72216364a571f22267c894b7281f35c3ab0095`. Antes de escribir nada en la placa, se vuelve a comprobar en el Mac:

```bash
python3 - << 'PY'
import hashlib, pathlib
path = pathlib.Path("flash_contents.bin")  # la ruta real de la copia, fuera de este repo
data = path.read_bytes()
digest = hashlib.sha256(data).hexdigest()
if len(data) != 16777216 or digest != "037b8878a1ad0e344ffc88eb7f72216364a571f22267c894b7281f35c3ab0095":
    raise SystemExit(f"copia no valida: {len(data)} bytes {digest}")
print("copia original intacta")
PY
```

Si esa comprobación falla, no se flashea.

## Qué construye la prueba

El cliente sigue siendo Xiaozhi `v2.5.2`, placa `waveshare/esp32-s3-touch-lcd-1.54`, idioma `es-ES`, sin la palabra de activación china. Encima va el aviso de movimiento de `firmware/`. La URL OTA por defecto no se cambia: el botón de hablar sigue pudiendo usar el servidor Xiaozhi que la unidad ya conoce. El aviso de caminar o estirar no usa ese servidor para el texto ni para la voz; solo espera a que el reloj se haya puesto con `server_time`.

```bash
python3 scripts/apply_hablaia.py --tree third_party/xiaozhi-esp32
```

`scripts/prepare_firmware.sh` clona el tag y aplica ese paso. Dentro del árbol, con ESP-IDF `release/v6.1` y `export.sh` ya cargado:

```bash
python scripts/build.py waveshare/esp32-s3-touch-lcd-1.54 \
  --name esp32-s3-touch-lcd-1.54 \
  --language es-ES \
  --wake-word disabled
```

La compilación hecha aquí con ESP-IDF v6.1.0 terminó en `build/xiaozhi.bin` (0x2b8c50 bytes; cabe en la partición de aplicación de 0x3f0000 y deja 0x1373b0 libres). `sdkconfig` quedó con `CONFIG_LANGUAGE_ES_ES`, `CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54` y `CONFIG_WAKE_WORD_DISABLED`. No se flasheó.

`build/flash_args` de esa compilación, que es lo que `idf.py flash` escribiría, lista piezas sueltas y no un solo binario fusionado:

```text
--flash-mode dio --flash-freq 80m --flash-size 16MB
0x0 bootloader/bootloader.bin
0x8000 partition_table/partition-table.bin
0xd000 ota_data_initial.bin
0x20000 xiaozhi.bin
0x800000 generated_assets.bin
```

En el Mac, desde `build/`, el equivalente que imprimió esptool v5.6.0 es `python -m esptool --chip esp32s3 -b 460800 --before default-reset --after hard-reset write-flash "@flash_args"`. No se ejecuta `erase-flash` antes.

## Qué se borra y qué se conserva

Esa lista no contiene la dirección `0x9000`. En `partitions/v2/16m.csv` la NVS ocupa `0x9000`–`0xCFFF`. La tabla de particiones mide 3072 bytes y cabe en el sector `0x8000`–`0x8FFF`. `ota_data_initial.bin` mide 8192 bytes y coincide con `otadata` en `0xd000`. La aplicación empieza en `0x20000` y no llega a `ota_1`. Los recursos empiezan en `0x800000`.

Con esos tamaños, la escritura sustituye en la placa:

- el gestor de arranque
- la tabla de particiones
- la elección de partición OTA
- la aplicación nueva en `ota_0`
- el principio de la partición `assets`

No está en la lista la NVS de `0x9000`. Si el firmware que hay ahora usa esa misma tabla, las claves Wi-Fi pueden seguir ahí. No se puede afirmar sin leer la imagen privada: si la tabla de origen era otra, hay que volver a entrar la Wi-Fi en `http://192.168.4.1`. No se escribe en ese formulario una URL de producción. Vacío, el aparato usa `https://api.tenclass.net/xiaozhi/ota/`.

No se queman eFuses. La copia del Mac no se modifica. Lo que quede en `ota_1` o al final de `assets` no sirve para volver atrás. La única restauración del programa original es el archivo de 16777216 bytes.

Un `merged-binary.bin` escrito en `0x0` sí rellena huecos con `0xFF`, incluida la NVS. Esta prueba no usa ese archivo.

## Cómo volver al binario original

Con la placa en el mismo puerto, y sin borrar antes:

```bash
esptool -p PORT -b 460800 write-flash 0x0 flash_contents.bin
esptool -p PORT -b 460800 read-flash 0 0x1000000 flash_verify.bin
python3 - << 'PY'
import hashlib, pathlib
data = pathlib.Path("flash_verify.bin").read_bytes()
digest = hashlib.sha256(data).hexdigest()
if len(data) != 16777216 or digest != "037b8878a1ad0e344ffc88eb7f72216364a571f22267c894b7281f35c3ab0095":
    raise SystemExit(f"restauracion distinta: {len(data)} {digest}")
print("flash original restaurada")
PY
```

`0x1000000` son los 16 MB. La lectura de comprobación tiene que coincidir byte a byte con la copia, no solo arrancar. El ZIP oficial `v2.5.2_waveshare-esp32-s3-touch-lcd-1.54.zip` es otra imagen Xiaozhi, en el idioma por defecto del release, y no devuelve el Wi-Fi ni el programa que había en la unidad.

## Cómo comprobar el aparato

1. El monitor serie, con `idf.py monitor` o la consola USB, muestra la placa Waveshare ESP32-S3-Touch-LCD-1.54. La pantalla usa textos de `es-ES`, por ejemplo «Modo configuración de red» al abrir el portal.
2. Tras guardar la Wi-Fi, el arranque pide la hora al servidor OTA. Hasta que esa respuesta trae `server_time`, el aviso no habla: un reloj en 1970 no es una hora de día.
3. El registro guarda el desfase que vino en `timezone_offset` y lo deshace. La ventana 09:00–21:00 es Europe/Madrid (`CET-1CEST,M3.5.0/2,M10.5.0/3`), aunque el servidor haya mandado otra zona. En el log de arranque aparece `Reminder 09:00-21:00 Europe/Madrid, every 180 min`.
4. Los avisos posibles son las 09:00, las 12:00, las 15:00 y las 18:00. Cada uno suena una sola vez, y solo durante los 10 minutos siguientes. Si el aparato está en conversación, ese turno se pierde; no se recupera más tarde ni se acumula con el siguiente.
5. Se ve el texto y se oye la misma frase en español, por ejemplo «Si le parece, dé unos pasos a su ritmo.» El estado en pantalla es «A su ritmo».
6. Una pulsación corta de PLUS (subir volumen, GPIO4) lo descarta. No vuelve a salir en ese turno. BOOT (bajar volumen, GPIO0) lo aplaza 30 minutos, una sola vez, y solo si esos 30 minutos siguen antes del siguiente turno y antes de las 21:00. Si no caben, el aviso se cierra y no vuelve por la noche.
7. Una pulsación corta de PWR sigue abriendo y cerrando la conversación. Si el aviso estaba en pantalla, esa pulsación además lo da por visto.
8. Fuera de 09:00–21:00 no hay aviso. Reiniciar dentro de los 10 minutos de un aviso ya mostrado no lo repite.
9. Subir o bajar el volumen funciona igual que antes cuando no hay un aviso en pantalla.

No hay en esta imagen un modo de acortar las tres horas. Cambiar el horario de prueba se hace con las claves NVS `start_min` y `end_min` (minutos desde medianoche; -1 en el código significa «usar 09:00 y 21:00»), no editando un secreto del repositorio. La zona compilada sigue siendo Europe/Madrid.
