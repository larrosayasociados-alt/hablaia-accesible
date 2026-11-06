#ifndef HABLAIA_REMINDER_H_
#define HABLAIA_REMINDER_H_

#include <stdbool.h>

/* Hooks used by the pinned Xiaozhi v2.5.2 tree. The talk button is not consumed. */

void HablaiaReminder_Init(void);
void HablaiaReminder_OnClockTick(bool server_time_ok, bool device_idle);
bool HablaiaReminder_OnVolumeUp(void);
bool HablaiaReminder_OnVolumeDown(void);
void HablaiaReminder_OnTalk(void);

#endif
