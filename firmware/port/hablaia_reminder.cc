#include "hablaia_reminder.h"

#include "hablaia_prompts.h"
#include "reminder_defaults.h"
#include "reminder_schedule.h"

#include "application.h"
#include "settings.h"

#include <esp_log.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

namespace {

constexpr const char* kTag = "hablaia";
constexpr const char* kNamespace = "hablaia";

HablaiaReminderConfig g_config;
HablaiaReminderState g_state;
bool g_inited = false;

void CopySetting(char* dest, const std::string& value) {
    snprintf(dest, kHablaiaSlotKeyLen, "%s", value.c_str());
}

void Load() {
    g_config = HablaiaDefaultConfig();
    memset(&g_state, 0, sizeof(g_state));
    Settings settings(kNamespace, false);
    const int start = settings.GetInt("start_min", -1);
    const int end = settings.GetInt("end_min", -1);
    const int snooze = settings.GetInt("snz_min", -1);
    if (start >= 0) {
        g_config.window_start_minute = start;
    }
    if (end >= 0) {
        g_config.window_end_minute = end;
    }
    if (snooze >= 0) {
        g_config.snooze_minutes = snooze;
    }
    g_config.enabled = settings.GetBool("enabled", true);
    if (!HablaiaConfigIsValid(&g_config)) {
        ESP_LOGW(kTag, "Reminder config in NVS is invalid; using the compiled daytime window");
        g_config = HablaiaDefaultConfig();
    }
    CopySetting(g_state.handled_slot, settings.GetString("handled"));
    CopySetting(g_state.snooze_slot, settings.GetString("snz_slot"));
    g_state.snooze_until_unix = settings.GetInt("snz_unix", 0);
    g_state.showing = settings.GetBool("showing", false);
}

void SaveState() {
    Settings settings(kNamespace, true);
    settings.SetString("handled", g_state.handled_slot);
    settings.SetString("snz_slot", g_state.snooze_slot);
    settings.SetInt("snz_unix", g_state.snooze_until_unix);
    settings.SetBool("showing", g_state.showing);
}

HablaiaClockReading ReadClock(bool server_time_ok) {
    Settings settings(kNamespace, false);
    HablaiaClockReading reading{};
    reading.device_unix = static_cast<int64_t>(time(nullptr));
    reading.ota_offset_minutes = settings.GetInt("ota_tz_min", 0);
    reading.time_ok = server_time_ok && settings.GetBool("time_ok", false);
    return reading;
}

bool Apply(HablaiaReminderInput input, bool server_time_ok, bool device_idle) {
    const HablaiaReminderState before = g_state;
    const HablaiaClockReading reading = ReadClock(server_time_ok);
    const HablaiaReminderDecision decision =
        HablaiaEvaluateReminder(&g_config, &g_state, &reading, device_idle, input);
    if (memcmp(&before, &g_state, sizeof(before)) != 0) {
        SaveState();
    }
    if (decision.effect == kHablaiaEffectPresent) {
        ESP_LOGI(kTag, "Movement reminder %s (OTA offset %d min)", decision.slot_key,
                 reading.ota_offset_minutes);
        Application::GetInstance().Alert(HablaiaReminderStatus(),
                                         HablaiaReminderText(decision.message_index), "neutral",
                                         HablaiaPromptOgg(decision.message_index));
    } else if (decision.effect == kHablaiaEffectClear) {
        Application::GetInstance().DismissAlert();
    }
    return decision.consume_button;
}

}  // namespace

void HablaiaReminder_Init(void) {
    if (g_inited) {
        return;
    }
    Load();
    HablaiaNormalizeAfterBoot(&g_state);
    SaveState();
    g_inited = true;
    ESP_LOGI(kTag, "Reminder %02d:%02d-%02d:%02d %s, every %d min, grace %d, snooze %d",
             g_config.window_start_minute / 60, g_config.window_start_minute % 60,
             g_config.window_end_minute / 60, g_config.window_end_minute % 60, HABLAIA_ZONE_NAME,
             g_config.interval_minutes, g_config.grace_minutes, g_config.snooze_minutes);
}

void HablaiaReminder_OnClockTick(bool server_time_ok, bool device_idle) {
    if (!g_inited) {
        HablaiaReminder_Init();
    }
    Apply(kHablaiaInputTick, server_time_ok, device_idle);
}

bool HablaiaReminder_OnVolumeUp(void) {
    if (!g_inited) {
        HablaiaReminder_Init();
    }
    return Apply(kHablaiaInputDismiss, true, true);
}

bool HablaiaReminder_OnVolumeDown(void) {
    if (!g_inited) {
        HablaiaReminder_Init();
    }
    return Apply(kHablaiaInputSnooze, true, true);
}

void HablaiaReminder_OnTalk(void) {
    if (!g_inited) {
        HablaiaReminder_Init();
    }
    Apply(kHablaiaInputTalk, true, true);
}
