#include "reminder_schedule.h"

#include <stdint.h>

namespace {

int64_t DaysFromCivil(int year, unsigned month, unsigned day) {
    year -= month <= 2;
    const int era = (year >= 0 ? year : year - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(year - era * 400);
    const unsigned doy = (153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return static_cast<int64_t>(era) * 146097 + static_cast<int64_t>(doe) - 719468;
}

void CivilFromDays(int64_t days, int* year, unsigned* month, unsigned* day) {
    days += 719468;
    const int64_t era = (days >= 0 ? days : days - 146096) / 146097;
    const unsigned doe = static_cast<unsigned>(days - era * 146097);
    const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    const int y = static_cast<int>(yoe) + static_cast<int>(era * 400);
    const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const unsigned mp = (5 * doy + 2) / 153;
    const unsigned d = doy - (153 * mp + 2) / 5 + 1;
    const unsigned m = mp < 10 ? mp + 3 : mp - 9;
    *year = y + (m <= 2);
    *month = m;
    *day = d;
}

int WeekdaySunday0(int year, unsigned month, unsigned day) {
    const int64_t days = DaysFromCivil(year, month, day);
    int weekday = static_cast<int>((days + 4) % 7);
    if (weekday < 0) {
        weekday += 7;
    }
    return weekday;
}

unsigned DaysInMonth(int year, unsigned month) {
    static const unsigned days[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (month == 2) {
        const bool leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
        return leap ? 29 : 28;
    }
    return days[month];
}

unsigned LastSunday(int year, unsigned month) {
    const unsigned last = DaysInMonth(year, month);
    return last - static_cast<unsigned>(WeekdaySunday0(year, month, last));
}

bool CivilFromUnixUtc(int64_t unix_utc, HablaiaCivilTime* out) {
    int64_t days = unix_utc / 86400;
    int sod = static_cast<int>(unix_utc % 86400);
    if (sod < 0) {
        sod += 86400;
        days -= 1;
    }
    unsigned month = 0;
    unsigned day = 0;
    CivilFromDays(days, &out->year, &month, &day);
    out->month = static_cast<int>(month);
    out->day = static_cast<int>(day);
    out->hour = sod / 3600;
    out->minute = (sod % 3600) / 60;
    out->second = sod % 60;
    return true;
}

int64_t UnixFromCivilUtc(const HablaiaCivilTime* civil) {
    const int64_t days = DaysFromCivil(civil->year, static_cast<unsigned>(civil->month),
                                       static_cast<unsigned>(civil->day));
    return days * 86400 + civil->hour * 3600 + civil->minute * 60 + civil->second;
}

bool SameCivil(const HablaiaCivilTime* a, const HablaiaCivilTime* b) {
    return a->year == b->year && a->month == b->month && a->day == b->day && a->hour == b->hour &&
           a->minute == b->minute && a->second == b->second;
}

/* EU rule since 1996: CEST is [last Sunday of March 01:00 UTC, last Sunday of October 01:00 UTC). */
bool IsCest(int64_t unix_utc) {
    HablaiaCivilTime utc{};
    CivilFromUnixUtc(unix_utc, &utc);
    HablaiaCivilTime start{utc.year, 3, static_cast<int>(LastSunday(utc.year, 3)), 1, 0, 0};
    HablaiaCivilTime end{utc.year, 10, static_cast<int>(LastSunday(utc.year, 10)), 1, 0, 0};
    const int64_t start_unix = UnixFromCivilUtc(&start);
    const int64_t end_unix = UnixFromCivilUtc(&end);
    return unix_utc >= start_unix && unix_utc < end_unix;
}

int MadridOffsetMinutes(int64_t unix_utc) {
    return IsCest(unix_utc) ? 120 : 60;
}

}  // namespace

bool HablaiaCivilFromUnix(int64_t unix_utc, HablaiaTimeZone zone, HablaiaCivilTime* out) {
    if (out == nullptr) {
        return false;
    }
    int64_t shifted = unix_utc;
    if (zone == kHablaiaZoneEuropeMadrid) {
        shifted += static_cast<int64_t>(MadridOffsetMinutes(unix_utc)) * 60;
    } else if (zone != kHablaiaZoneUtc) {
        return false;
    }
    return CivilFromUnixUtc(shifted, out);
}

bool HablaiaUnixFromCivil(const HablaiaCivilTime* civil, HablaiaTimeZone zone, int64_t* out_unix) {
    if (civil == nullptr || out_unix == nullptr) {
        return false;
    }
    if (civil->month < 1 || civil->month > 12 || civil->day < 1 ||
        civil->day > static_cast<int>(DaysInMonth(civil->year, static_cast<unsigned>(civil->month))) ||
        civil->hour < 0 || civil->hour > 23 || civil->minute < 0 || civil->minute > 59 ||
        civil->second < 0 || civil->second > 59) {
        return false;
    }
    if (zone == kHablaiaZoneUtc) {
        *out_unix = UnixFromCivilUtc(civil);
        return true;
    }
    if (zone != kHablaiaZoneEuropeMadrid) {
        return false;
    }

    bool found = false;
    int64_t chosen = 0;
    const int offsets[] = {60, 120};
    for (int offset : offsets) {
        const int64_t guess = UnixFromCivilUtc(civil) - static_cast<int64_t>(offset) * 60;
        if (MadridOffsetMinutes(guess) != offset) {
            continue;
        }
        HablaiaCivilTime back{};
        HablaiaCivilFromUnix(guess, kHablaiaZoneEuropeMadrid, &back);
        if (!SameCivil(&back, civil)) {
            continue;
        }
        if (!found || guess > chosen) {
            chosen = guess;
            found = true;
        }
    }
    if (!found) {
        return false;
    }
    *out_unix = chosen;
    return true;
}

bool HablaiaLocalFromReading(const HablaiaClockReading* reading, HablaiaTimeZone zone,
                             HablaiaCivilTime* out) {
    if (reading == nullptr || !reading->time_ok) {
        return false;
    }
    if (reading->ota_offset_minutes < -14 * 60 || reading->ota_offset_minutes > 14 * 60) {
        return false;
    }
    const int64_t utc = reading->device_unix - static_cast<int64_t>(reading->ota_offset_minutes) * 60;
    if (!HablaiaCivilFromUnix(utc, zone, out)) {
        return false;
    }
    return out->year >= 2024;
}
