# HablaIA Accesible

Prototipo en español para la placa Waveshare ESP32-S3-Touch-LCD-1.54. Usa el cliente oficial [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) `v2.5.2` (commit `49b4380b3faa0ceadd28a3e78aaf0f311c46c57e`), que ya incluye esta placa. No anade un firmware de placa propio.

La unidad comprada arranca con el firmware Xiaozhi y con Wi-Fi. La lectura completa de esa flash ya está en el Mac (16777216 bytes, SHA-256 `037b8878a1ad0e344ffc88eb7f72216364a571f22267c894b7281f35c3ab0095`). Este repositorio no contiene esa copia. No se flashea nada desde aquí.

## Conclusion

Sí. Se puede usar Xiaozhi sin escribir otro soporte de placa. El release `v2.5.2` publica `v2.5.2_waveshare-esp32-s3-touch-lcd-1.54.zip` y el código de `main/boards/waveshare/esp32-s3-touch-lcd-1.54` inicializa ST7789, CST816, ES8311, ES7210 y el AEC. El idioma `es-ES` ya existe. Encima, `firmware/` añade el aviso diurno para caminar o estirar: horario, texto, audio Opus y botones. La persona **Asistente senior** sigue en el servidor, en `config/persona/asistente-senior.es.json`.

El IMU QMI8658 y la ranura MicroSD estan en la placa y el cliente oficial no los inicia. Hacen falta solo si mas adelante se quieren caidas o archivos locales.

## Contenido

| Ruta | Para que |
| --- | --- |
| `docs/HARDWARE.md` | Placa, versiones, comandos citados y la copia original |
| `docs/PRUEBA.md` | Qué borra la primera escritura, qué conserva y cómo volver atrás |
| `docs/ARQUITECTURA.md` | Qué ya hace el firmware y qué espera un servidor HablaIA |
| `firmware/` | Aviso de movimiento, comprobable en el ordenador de desarrollo |
| `config/upstream-pin.json` | Tag, commit y hashes de los archivos citados |
| `config/build-profile.json` | `es-ES`, palabra de activacion desactivada, misma placa |
| `config/persona/asistente-senior.es.json` | Instruccion de sistema en espanol |
| `config/backend/` | Ejemplo de respuesta OTA con `example.invalid` |

## Comprobar sin flashear

```bash
python3 scripts/check_prototype.py
python3 scripts/verify_upstream.py
python3 scripts/generate_prompts.py
python3 scripts/apply_hablaia.py --check
scripts/test_reminder.sh
scripts/print_build.sh
```

`print_build.sh` solo imprime los comandos del tag. Si se le pasa `flash`, termina con error.

La compilación del firmware pide ESP-IDF `release/v6.1`. La prueba en la placa, qué se borra y cómo volver al binario original están en `docs/PRUEBA.md`.
