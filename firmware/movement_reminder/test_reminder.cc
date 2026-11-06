#include "reminder_schedule.h"
#include "reminder_defaults.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int g_failures = 0;

static void Expect(bool condition, const char* message) {
    if (!condition) {
        fprintf(stderr, "FAIL %s\n", message);
        g_failures++;
    }
}

static HablaiaClockReading ClockAt(int64_t device_unix, int offset_minutes) {
    HablaiaClockReading reading{};
    reading.device_unix = device_unix;
    reading.ota_offset_minutes = offset_minutes;
    reading.time_ok = true;
    return reading;
}

static int64_t Utc(int year, int month, int day, int hour, int minute, int second) {
    HablaiaCivilTime civil{year, month, day, hour, minute, second};
    int64_t unix_utc = 0;
    if (!HablaiaUnixFromCivil(&civil, kHablaiaZoneUtc, &unix_utc)) {
        fprintf(stderr, "FAIL could not build UTC %04d-%02d-%02d %02d:%02d:%02d\n", year, month, day,
                hour, minute, second);
        g_failures++;
    }
    return unix_utc;
}

static HablaiaReminderDecision Tick(const HablaiaReminderConfig* config, HablaiaReminderState* state,
                                    int64_t device_unix, int offset, bool idle) {
    const HablaiaClockReading reading = ClockAt(device_unix, offset);
    return HablaiaEvaluateReminder(config, state, &reading, idle, kHablaiaInputTick);
}

static void ExpectCivil(int64_t unix_utc, int hour, int minute, const char* label) {
    HablaiaCivilTime civil{};
    Expect(HablaiaCivilFromUnix(unix_utc, kHablaiaZoneEuropeMadrid, &civil), label);
    if (civil.hour != hour || civil.minute != minute) {
        fprintf(stderr, "FAIL %s got %02d:%02d\n", label, civil.hour, civil.minute);
        g_failures++;
    }
}

static void ExpectMatchesLibc(int64_t unix_utc) {
    HablaiaCivilTime civil{};
    Expect(HablaiaCivilFromUnix(unix_utc, kHablaiaZoneEuropeMadrid, &civil), "madrid conversion");
    struct tm broken{};
    const time_t instant = static_cast<time_t>(unix_utc);
    if (localtime_r(&instant, &broken) == nullptr) {
        fprintf(stderr, "FAIL localtime_r\n");
        g_failures++;
        return;
    }
    if (broken.tm_year + 1900 != civil.year || broken.tm_mon + 1 != civil.month ||
        broken.tm_mday != civil.day || broken.tm_hour != civil.hour || broken.tm_min != civil.minute ||
        broken.tm_sec != civil.second) {
        fprintf(stderr, "FAIL libc mismatch unix %lld ours %04d-%02d-%02d %02d:%02d:%02d libc %04d-%02d-%02d %02d:%02d:%02d\n",
                static_cast<long long>(unix_utc), civil.year, civil.month, civil.day, civil.hour, civil.minute,
                civil.second, broken.tm_year + 1900, broken.tm_mon + 1, broken.tm_mday, broken.tm_hour,
                broken.tm_min, broken.tm_sec);
        g_failures++;
    }
}

static void TestClock() {
    setenv("TZ", HABLAIA_POSIX_TZ, 1);
    tzset();
    ExpectCivil(Utc(2026, 1, 15, 8, 0, 0), 9, 0, "winter 09:00");
    ExpectCivil(Utc(2026, 7, 15, 7, 0, 0), 9, 0, "summer 09:00");
    ExpectCivil(Utc(2026, 3, 29, 0, 30, 0), 1, 30, "before spring forward");
    ExpectCivil(Utc(2026, 3, 29, 1, 30, 0), 3, 30, "after spring forward");
    ExpectCivil(Utc(2026, 10, 25, 0, 30, 0), 2, 30, "before fall back");
    ExpectCivil(Utc(2026, 10, 25, 1, 30, 0), 2, 30, "after fall back");

    const int64_t samples[] = {
        Utc(2026, 1, 15, 8, 0, 0),  Utc(2026, 3, 29, 0, 30, 0), Utc(2026, 3, 29, 1, 0, 0),
        Utc(2026, 3, 29, 1, 30, 0), Utc(2026, 7, 15, 7, 0, 0), Utc(2026, 10, 25, 1, 0, 0),
        Utc(2026, 10, 25, 1, 30, 0), Utc(2026, 12, 31, 22, 30, 0),
    };
    for (int64_t sample : samples) {
        ExpectMatchesLibc(sample);
        int64_t roundtrip = 0;
        HablaiaCivilTime civil{};
        HablaiaCivilFromUnix(sample, kHablaiaZoneEuropeMadrid, &civil);
        Expect(HablaiaUnixFromCivil(&civil, kHablaiaZoneEuropeMadrid, &roundtrip), "inverse");
        Expect(roundtrip == sample, "madrid roundtrip");
    }

    HablaiaCivilTime missing{2026, 3, 29, 2, 30, 0};
    int64_t unused = 0;
    Expect(!HablaiaUnixFromCivil(&missing, kHablaiaZoneEuropeMadrid, &unused), "spring gap is not a time");

    HablaiaCivilTime folded{2026, 10, 25, 2, 30, 0};
    Expect(HablaiaUnixFromCivil(&folded, kHablaiaZoneEuropeMadrid, &unused), "ambiguous hour has one chosen instant");
    Expect(unused == Utc(2026, 10, 25, 1, 30, 0), "ambiguous hour uses CET, the later instant");
}

static void TestSchedule() {
    const HablaiaReminderConfig config = HablaiaDefaultConfig();
    Expect(HablaiaConfigIsValid(&config), "default config");
    Expect(config.interval_minutes == 180, "three hours");
    Expect(config.window_start_minute == 9 * 60 && config.window_end_minute == 21 * 60, "daytime window");

    const int64_t morning = Utc(2026, 1, 15, 8, 0, 0);
    HablaiaReminderState state{};
    HablaiaReminderDecision decision = Tick(&config, &state, morning, 0, true);
    Expect(decision.effect == kHablaiaEffectPresent, "09:00 Madrid presents");
    Expect(decision.message_index == 0, "first phrase");
    Expect(strcmp(HablaiaReminderText(0), "Si le parece, dé unos pasos a su ritmo.") == 0, "phrase 0");
    Expect(state.showing, "showing");

    decision = Tick(&config, &state, morning + 30, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "does not replay while showing");

    const HablaiaClockReading reading = ClockAt(morning + 40, 0);
    decision = HablaiaEvaluateReminder(&config, &state, &reading, true, kHablaiaInputDismiss);
    Expect(decision.consume_button && decision.effect == kHablaiaEffectClear, "dismiss");
    Expect(!state.showing && state.snooze_slot[0] == '\0', "dismiss clears snooze");
    decision = Tick(&config, &state, morning + 120, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "dismissed slot stays quiet");

    HablaiaNormalizeAfterBoot(&state);
    decision = Tick(&config, &state, morning + 180, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "reboot does not replay the handled slot");

    decision = Tick(&config, &state, morning + 8 * 60, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "grace ends at ten minutes");

    HablaiaReminderState missed{};
    decision = Tick(&config, &missed, morning + 3 * 3600 + 30 * 60, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "a missed slot is not delivered late");
    decision = Tick(&config, &missed, Utc(2026, 1, 15, 11, 0, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectPresent && decision.message_index == 1, "next slot is independent");

    HablaiaReminderState busy{};
    decision = Tick(&config, &busy, morning, 0, false);
    Expect(decision.effect == kHablaiaEffectNone && !busy.showing, "conversation blocks the reminder");
    decision = Tick(&config, &busy, morning + 4 * 60, 0, true);
    Expect(decision.effect == kHablaiaEffectPresent, "it can still appear inside the grace period");

    HablaiaReminderState late_talk{};
    Tick(&config, &late_talk, morning, 0, false);
    decision = Tick(&config, &late_talk, morning + 10 * 60, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "after grace it is missed, not stacked");

    HablaiaReminderState snoozed{};
    Tick(&config, &snoozed, Utc(2026, 1, 15, 11, 0, 0), 0, true);
    const HablaiaClockReading noon = ClockAt(Utc(2026, 1, 15, 11, 1, 0), 0);
    decision = HablaiaEvaluateReminder(&config, &snoozed, &noon, true, kHablaiaInputSnooze);
    Expect(decision.consume_button && !snoozed.showing && snoozed.snooze_slot[0] != '\0', "snooze arms");
    decision = Tick(&config, &snoozed, Utc(2026, 1, 15, 11, 30, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "snooze waits");
    decision = Tick(&config, &snoozed, Utc(2026, 1, 15, 11, 31, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectPresent && decision.message_index == 1, "snooze speaks once");
    const HablaiaClockReading after = ClockAt(Utc(2026, 1, 15, 11, 32, 0), 0);
    HablaiaEvaluateReminder(&config, &snoozed, &after, true, kHablaiaInputDismiss);
    decision = Tick(&config, &snoozed, Utc(2026, 1, 15, 11, 40, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "snooze does not repeat");

    HablaiaReminderState crossed{};
    decision = Tick(&config, &crossed, Utc(2026, 1, 15, 14, 0, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectPresent, "15:00 Madrid is shown before the crossing snooze");
    const HablaiaClockReading near_next = ClockAt(Utc(2026, 1, 15, 16, 40, 0), 0);
    decision = HablaiaEvaluateReminder(&config, &crossed, &near_next, true, kHablaiaInputSnooze);
    Expect(decision.effect == kHablaiaEffectClear && crossed.snooze_slot[0] == '\0',
           "snooze that would cross the next slot is dropped");
    decision = Tick(&config, &crossed, Utc(2026, 1, 15, 17, 10, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "dropped snooze does not speak after the next slot");

    HablaiaReminderState night{};
    decision = Tick(&config, &night, Utc(2026, 1, 15, 20, 30, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "21:30 Madrid is outside the window");
    decision = Tick(&config, &night, Utc(2026, 1, 15, 7, 30, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "08:30 Madrid is outside the window");
    decision = Tick(&config, &night, Utc(2026, 1, 15, 20, 0, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "21:00 is the exclusive end");

    HablaiaReminderState evening{};
    decision = Tick(&config, &evening, Utc(2026, 1, 15, 17, 0, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectPresent && decision.message_index == 3, "18:00 uses the fourth phrase");
    const HablaiaClockReading late = ClockAt(Utc(2026, 1, 15, 19, 40, 0), 0);
    decision = HablaiaEvaluateReminder(&config, &evening, &late, true, kHablaiaInputSnooze);
    Expect(evening.snooze_slot[0] == '\0', "snooze past 21:00 is not kept");

    HablaiaReminderState shanghai{};
    const int64_t utc_morning = Utc(2026, 1, 15, 8, 0, 0);
    const int shanghai_offset = 480;
    decision = Tick(&config, &shanghai, utc_morning + shanghai_offset * 60, shanghai_offset, true);
    Expect(decision.effect == kHablaiaEffectPresent, "Shanghai OTA offset still means 09:00 in Madrid");

    HablaiaClockReading unset = ClockAt(utc_morning, 0);
    unset.time_ok = false;
    HablaiaReminderState unsynced{};
    decision = HablaiaEvaluateReminder(&config, &unsynced, &unset, true, kHablaiaInputTick);
    Expect(decision.effect == kHablaiaEffectNone, "no reminder before the clock is set");

    HablaiaClockReading epoch = ClockAt(Utc(1970, 1, 1, 8, 0, 0), 0);
    decision = HablaiaEvaluateReminder(&config, &unsynced, &epoch, true, kHablaiaInputTick);
    Expect(decision.effect == kHablaiaEffectNone, "epoch is not a daytime slot");

    HablaiaReminderState tomorrow{};
    Tick(&config, &tomorrow, morning, 0, true);
    HablaiaEvaluateReminder(&config, &tomorrow, &reading, true, kHablaiaInputDismiss);
    decision = Tick(&config, &tomorrow, Utc(2026, 1, 16, 8, 0, 0), 0, true);
    Expect(decision.effect == kHablaiaEffectPresent, "the next morning is a new slot");

    HablaiaReminderState talk{};
    Tick(&config, &talk, morning, 0, true);
    const HablaiaClockReading talk_now = ClockAt(morning + 5, 0);
    decision = HablaiaEvaluateReminder(&config, &talk, &talk_now, true, kHablaiaInputTalk);
    Expect(!decision.consume_button && decision.effect == kHablaiaEffectClear, "talk still belongs to the button");
    decision = Tick(&config, &talk, morning + 60, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "talk acknowledges the slot");

    HablaiaReminderConfig disabled = config;
    disabled.enabled = false;
    HablaiaReminderState off{};
    decision = Tick(&disabled, &off, morning, 0, true);
    Expect(decision.effect == kHablaiaEffectNone, "disabled");

    const HablaiaClockReading idle = ClockAt(morning, 0);
    HablaiaReminderState hidden{};
    decision = HablaiaEvaluateReminder(&config, &hidden, &idle, true, kHablaiaInputDismiss);
    Expect(!decision.consume_button, "volume dismiss is ignored when nothing is showing");
}

int main() {
    TestClock();
    TestSchedule();
    if (g_failures != 0) {
        fprintf(stderr, "%d failure(s)\n", g_failures);
        return 1;
    }
    printf("reminder schedule ok\n");
    return 0;
}
