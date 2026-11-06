#ifndef HABLAIA_REMINDER_SCHEDULE_H_
#define HABLAIA_REMINDER_SCHEDULE_H_

#include <stdbool.h>
#include <stdint.h>

enum { kHablaiaSlotKeyLen = 16 };

enum HablaiaTimeZone {
    kHablaiaZoneUtc = 0,
    kHablaiaZoneEuropeMadrid = 1
};

struct HablaiaCivilTime {
    int year;
    int month;
    int day;
    int hour;
    int minute;
    int second;
};

struct HablaiaReminderConfig {
    int window_start_minute;
    int window_end_minute;
    int interval_minutes;
    int grace_minutes;
    int snooze_minutes;
    bool enabled;
    HablaiaTimeZone zone;
};

/* device_unix is whatever time() returns. Xiaozhi adds the OTA timezone_offset
 * into that clock before settimeofday. ota_offset_minutes is that same value,
 * so UTC is device_unix - ota_offset_minutes * 60. */
struct HablaiaClockReading {
    int64_t device_unix;
    int ota_offset_minutes;
    bool time_ok;
};

struct HablaiaReminderState {
    char handled_slot[kHablaiaSlotKeyLen];
    char snooze_slot[kHablaiaSlotKeyLen];
    int32_t snooze_until_unix;
    bool showing;
};

enum HablaiaReminderInput {
    kHablaiaInputTick = 0,
    kHablaiaInputDismiss = 1,
    kHablaiaInputSnooze = 2,
    kHablaiaInputTalk = 3
};

enum HablaiaReminderEffect {
    kHablaiaEffectNone = 0,
    kHablaiaEffectPresent = 1,
    kHablaiaEffectClear = 2
};

struct HablaiaReminderDecision {
    HablaiaReminderEffect effect;
    bool consume_button;
    char slot_key[kHablaiaSlotKeyLen];
    int message_index;
};

HablaiaReminderConfig HablaiaDefaultConfig(void);
bool HablaiaConfigIsValid(const HablaiaReminderConfig* config);
const char* HablaiaReminderText(int message_index);
const char* HablaiaReminderStatus(void);

bool HablaiaCivilFromUnix(int64_t unix_utc, HablaiaTimeZone zone, HablaiaCivilTime* out);
bool HablaiaUnixFromCivil(const HablaiaCivilTime* civil, HablaiaTimeZone zone, int64_t* out_unix);
bool HablaiaLocalFromReading(const HablaiaClockReading* reading, HablaiaTimeZone zone,
                             HablaiaCivilTime* out);

void HablaiaNormalizeAfterBoot(HablaiaReminderState* state);

HablaiaReminderDecision HablaiaEvaluateReminder(const HablaiaReminderConfig* config,
                                                HablaiaReminderState* state,
                                                const HablaiaClockReading* reading,
                                                bool device_idle,
                                                HablaiaReminderInput input);

#endif
