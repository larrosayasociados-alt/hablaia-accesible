# HablaIA Accesible

Prototipo en español para la placa Waveshare ESP32-S3-Touch-LCD-1.54. Usa el cliente oficial [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) `v2.5.2` (commit `49b4380b3faa0ceadd28a3e78aaf0f311c46c57e`), que ya incluye esta placa. No anade un firmware de placa propio.

La unidad comprada arranca hoy con el firmware Xiaozhi en chino y con Wi-Fi. Una lectura de solo lectura de esa flash se esta haciendo en el Mac. Este repositorio no contiene esa copia y no la da por completa. No se flashea nada desde aqui.

## Conclusion

Si. Se puede usar Xiaozhi sin escribir el soporte de la placa. El release `v2.5.2` publica `v2.5.2_waveshare-esp32-s3-touch-lcd-1.54.zip` y el codigo de `main/boards/waveshare/esp32-s3-touch-lcd-1.54` inicializa ST7789, CST816, ES8311, ES7210 y el AEC de la placa. El idioma `es-ES` ya existe en el cliente. La persona **Asistente senior** vive en el servidor, en `config/persona/asistente-senior.es.json`, no en la flash.

El IMU QMI8658 y la ranura MicroSD estan en la placa y el cliente oficial no los inicia. Hacen falta solo si mas adelante se quieren caidas o archivos locales.

## Contenido

| Ruta | Para que |
| --- | --- |
| `docs/HARDWARE.md` | Placa, versiones, comandos citados y recuperacion |
| `docs/ARQUITECTURA.md` | Como apuntar a un servidor HablaIA sin secretos en git |
| `config/upstream-pin.json` | Tag, commit y hashes de los archivos citados |
| `config/build-profile.json` | `es-ES`, palabra de activacion desactivada, misma placa |
| `config/persona/asistente-senior.es.json` | Instruccion de sistema en espanol |
| `config/backend/` | Ejemplo de respuesta OTA con `example.invalid` |

## Comprobar sin flashear

```bash
python3 scripts/check_prototype.py
python3 scripts/verify_upstream.py
scripts/print_build.sh
```

`print_build.sh` solo imprime los comandos del tag. Si se le pasa `flash`, termina con error.

La compilacion real pide ESP-IDF `release/v6.1`, que es la rama que el README del cliente recomienda, y se hace en el Mac despues de cerrar y comprobar la copia de la flash. Los pasos estan en `docs/HARDWARE.md`.
