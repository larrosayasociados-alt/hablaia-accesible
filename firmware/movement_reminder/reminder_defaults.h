#ifndef HABLAIA_REMINDER_DEFAULTS_H_
#define HABLAIA_REMINDER_DEFAULTS_H_

/* Valores de config/reminder/daytime.json. scripts/check_prototype.py los compara. */

#define HABLAIA_ZONE_NAME "Europe/Madrid"
#define HABLAIA_POSIX_TZ "CET-1CEST,M3.5.0/2,M10.5.0/3"
#define HABLAIA_WINDOW_START_MINUTE (9 * 60)
#define HABLAIA_WINDOW_END_MINUTE (21 * 60)
#define HABLAIA_INTERVAL_MINUTES 180
#define HABLAIA_GRACE_MINUTES 10
#define HABLAIA_SNOOZE_MINUTES 30
#define HABLAIA_STATUS "A su ritmo"
#define HABLAIA_MESSAGE_0 "Si le parece, dé unos pasos a su ritmo."
#define HABLAIA_MESSAGE_1 "Puede estirarse un momento, con suavidad."
#define HABLAIA_MESSAGE_2 "Un pequeño paseo, solo si le apetece."
#define HABLAIA_MESSAGE_3 "Si quiere, mueva los hombros con calma."
#define HABLAIA_MESSAGE_COUNT 4

#endif
