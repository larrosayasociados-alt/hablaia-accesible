#include "reminder_schedule.h"
#include "reminder_defaults.h"

#include <stdio.h>
#include <string.h>

namespace {

void ClearKey(char* key) {
    key[0] = '\0';
}

bool KeyEquals(const char* key, const char* other) {
    return strncmp(key, other, kHablaiaSlotKeyLen) == 0;
}

void CopyKey(char* dest, const char* src) {
    snprintf(dest, kHablaiaSlotKeyLen, "%s", src);
}

bool FormatSlotKey(const HablaiaCivilTime* day, int minute_of_day, char* key) {
    if (minute_of_day < 0 || minute_of_day >= 24 * 60) {
        return false;
    }
    snprintf(key, kHablaiaSlotKeyLen, "%04d%02d%02dT%02d%02d", day->year, day->month, day->day,
             minute_of_day / 60, minute_of_day % 60);
    return true;
}

bool ParseSlotKey(const char* key, HablaiaCivilTime* day, int* minute_of_day) {
    int year = 0;
    int month = 0;
    int dom = 0;
    int hour = 0;
    int minute = 0;
    if (sscanf(key, "%4d%2d%2dT%2d%2d", &year, &month, &dom, &hour, &minute) != 5) {
        return false;
    }
    char roundtrip[kHablaiaSlotKeyLen];
    snprintf(roundtrip, sizeof(roundtrip), "%04d%02d%02dT%02d%02d", year, month, dom, hour, minute);
    if (strncmp(roundtrip, key, kHablaiaSlotKeyLen) != 0) {
        return false;
    }
    day->year = year;
    day->month = month;
    day->day = dom;
    day->hour = hour;
    day->minute = minute;
    day->second = 0;
    *minute_of_day = hour * 60 + minute;
    return true;
}

struct DueSlot {
    bool due;
    char key[kHablaiaSlotKeyLen];
    int minute_of_day;
    int index;
};

DueSlot CurrentDueSlot(const HablaiaReminderConfig* config, const HablaiaCivilTime* local) {
    DueSlot slot{};
    const int now_minute = local->hour * 60 + local->minute;
    if (now_minute < config->window_start_minute || now_minute >= config->window_end_minute) {
        return slot;
    }
    const int index = (now_minute - config->window_start_minute) / config->interval_minutes;
    const int slot_minute = config->window_start_minute + index * config->interval_minutes;
    if (slot_minute >= config->window_end_minute) {
        return slot;
    }
    const int elapsed = (now_minute - slot_minute) * 60 + local->second;
    if (elapsed < 0 || elapsed >= config->grace_minutes * 60) {
        return slot;
    }
    if (!FormatSlotKey(local, slot_minute, slot.key)) {
        return slot;
    }
    slot.due = true;
    slot.minute_of_day = slot_minute;
    slot.index = index;
    return slot;
}

bool DeviceUnixForCivil(const HablaiaCivilTime* civil, HablaiaTimeZone zone, int ota_offset_minutes,
                        int64_t* device_unix) {
    int64_t utc = 0;
    if (!HablaiaUnixFromCivil(civil, zone, &utc)) {
        return false;
    }
    *device_unix = utc + static_cast<int64_t>(ota_offset_minutes) * 60;
    return true;
}

bool SnoozeStillInsideSlot(const HablaiaReminderConfig* config, const HablaiaReminderState* state,
                           int ota_offset_minutes, int32_t snooze_until, int64_t* boundary_unix) {
    HablaiaCivilTime slot_time{};
    int slot_minute = 0;
    if (!ParseSlotKey(state->snooze_slot, &slot_time, &slot_minute)) {
        return false;
    }
    int next_minute = slot_minute + config->interval_minutes;
    if (next_minute > config->window_end_minute) {
        next_minute = config->window_end_minute;
    }
    HablaiaCivilTime boundary = slot_time;
    boundary.hour = next_minute / 60;
    boundary.minute = next_minute % 60;
    boundary.second = 0;
    if (!DeviceUnixForCivil(&boundary, config->zone, ota_offset_minutes, boundary_unix)) {
        return false;
    }
    return snooze_until < *boundary_unix;
}

HablaiaReminderDecision None() {
    HablaiaReminderDecision decision{};
    decision.effect = kHablaiaEffectNone;
    decision.message_index = -1;
    return decision;
}

HablaiaReminderDecision Present(HablaiaReminderState* state, const char* key, int index) {
    char key_copy[kHablaiaSlotKeyLen];
    CopyKey(key_copy, key);
    CopyKey(state->handled_slot, key_copy);
    ClearKey(state->snooze_slot);
    state->snooze_until_unix = 0;
    state->showing = true;
    HablaiaReminderDecision decision{};
    decision.effect = kHablaiaEffectPresent;
    decision.message_index = index;
    CopyKey(decision.slot_key, key_copy);
    return decision;
}

void Acknowledge(HablaiaReminderState* state) {
    state->showing = false;
    ClearKey(state->snooze_slot);
    state->snooze_until_unix = 0;
}

}  // namespace

HablaiaReminderConfig HablaiaDefaultConfig(void) {
    HablaiaReminderConfig config{};
    config.window_start_minute = HABLAIA_WINDOW_START_MINUTE;
    config.window_end_minute = HABLAIA_WINDOW_END_MINUTE;
    config.interval_minutes = HABLAIA_INTERVAL_MINUTES;
    config.grace_minutes = HABLAIA_GRACE_MINUTES;
    config.snooze_minutes = HABLAIA_SNOOZE_MINUTES;
    config.enabled = true;
    config.zone = kHablaiaZoneEuropeMadrid;
    return config;
}

bool HablaiaConfigIsValid(const HablaiaReminderConfig* config) {
    if (config == nullptr) {
        return false;
    }
    if (config->zone != kHablaiaZoneUtc && config->zone != kHablaiaZoneEuropeMadrid) {
        return false;
    }
    if (config->window_start_minute < 0 || config->window_end_minute > 24 * 60 ||
        config->window_start_minute >= config->window_end_minute) {
        return false;
    }
    if (config->interval_minutes < 30 || config->interval_minutes > 12 * 60) {
        return false;
    }
    if (config->grace_minutes < 1 || config->grace_minutes >= config->interval_minutes) {
        return false;
    }
    if (config->snooze_minutes < 1 || config->snooze_minutes > 180) {
        return false;
    }
    return true;
}

const char* HablaiaReminderText(int message_index) {
    static const char* kMessages[HABLAIA_MESSAGE_COUNT] = {
        HABLAIA_MESSAGE_0,
        HABLAIA_MESSAGE_1,
        HABLAIA_MESSAGE_2,
        HABLAIA_MESSAGE_3,
    };
    if (message_index < 0 || message_index >= HABLAIA_MESSAGE_COUNT) {
        return kMessages[0];
    }
    return kMessages[message_index];
}

const char* HablaiaReminderStatus(void) {
    return HABLAIA_STATUS;
}

void HablaiaNormalizeAfterBoot(HablaiaReminderState* state) {
    if (state != nullptr) {
        state->showing = false;
    }
}

HablaiaReminderDecision HablaiaEvaluateReminder(const HablaiaReminderConfig* config,
                                                HablaiaReminderState* state,
                                                const HablaiaClockReading* reading,
                                                bool device_idle, HablaiaReminderInput input) {
    if (config == nullptr || state == nullptr || reading == nullptr || !HablaiaConfigIsValid(config)) {
        return None();
    }

    HablaiaCivilTime local{};
    const bool clock_ok = HablaiaLocalFromReading(reading, config->zone, &local);

    if (input == kHablaiaInputDismiss || input == kHablaiaInputSnooze || input == kHablaiaInputTalk) {
        if (!state->showing) {
            return None();
        }
        HablaiaReminderDecision decision = None();
        decision.consume_button = input != kHablaiaInputTalk;
        decision.effect = kHablaiaEffectClear;
        if (input == kHablaiaInputSnooze && clock_ok && config->enabled) {
            const int32_t until = static_cast<int32_t>(reading->device_unix +
                                                       static_cast<int64_t>(config->snooze_minutes) * 60);
            int64_t boundary = 0;
            CopyKey(state->snooze_slot, state->handled_slot);
            state->snooze_until_unix = until;
            if (SnoozeStillInsideSlot(config, state, reading->ota_offset_minutes, until, &boundary)) {
                state->showing = false;
                return decision;
            }
            ClearKey(state->snooze_slot);
            state->snooze_until_unix = 0;
        }
        Acknowledge(state);
        return decision;
    }

    if (!config->enabled || !clock_ok || state->showing || !device_idle) {
        return None();
    }

    if (state->snooze_slot[0] != '\0') {
        int64_t boundary = 0;
        const bool inside = SnoozeStillInsideSlot(config, state, reading->ota_offset_minutes,
                                                   state->snooze_until_unix, &boundary);
        if (!inside || reading->device_unix >= boundary) {
            ClearKey(state->snooze_slot);
            state->snooze_until_unix = 0;
        } else if (reading->device_unix >= state->snooze_until_unix) {
            HablaiaCivilTime slot_time{};
            int slot_minute = 0;
            ParseSlotKey(state->snooze_slot, &slot_time, &slot_minute);
            const int index =
                (slot_minute - config->window_start_minute) / config->interval_minutes;
            return Present(state, state->snooze_slot, index % HABLAIA_MESSAGE_COUNT);
        }
    }

    const DueSlot due = CurrentDueSlot(config, &local);
    if (!due.due || KeyEquals(state->handled_slot, due.key)) {
        return None();
    }
    return Present(state, due.key, due.index % HABLAIA_MESSAGE_COUNT);
}
