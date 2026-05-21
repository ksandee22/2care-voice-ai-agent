import re
from datetime import time
from typing import Optional

# Canonical display format: "2:00 PM" (no leading zero on hour)
_TIME_ALIASES: dict[str, time] = {
    "9": time(9, 0),
    "9:00": time(9, 0),
    "9:00 am": time(9, 0),
    "9 am": time(9, 0),
    "09:00": time(9, 0),
    "10:30": time(10, 30),
    "10:30 am": time(10, 30),
    "10:30am": time(10, 30),
    "2": time(14, 0),
    "2:00": time(14, 0),
    "2:00 pm": time(14, 0),
    "2:00pm": time(14, 0),
    "2 pm": time(14, 0),
    "2pm": time(14, 0),
    "14:00": time(14, 0),
    "4:30": time(16, 30),
    "4:30 pm": time(16, 30),
    "4:30pm": time(16, 30),
    "4 pm": time(16, 30),
    "16:30": time(16, 30),
}


def normalize_time_input(text: str) -> str:
    """Normalize user/LLM time strings for lookup."""
    t = (text or "").strip().lower()
    t = t.replace(".", "")
    t = re.sub(r"\s+", " ", t)
    # "2:00 pm" / "2:00pm" -> consistent
    t = re.sub(r"(\d)(am|pm)", r"\1 \2", t)
    t = re.sub(r"(\d:\d{2})(am|pm)", r"\1 \2", t)
    return t.strip()


def parse_time_slot(text: str) -> Optional[time]:
    if not text or not str(text).strip():
        return None

    normalized = normalize_time_input(str(text))
    if normalized in _TIME_ALIASES:
        return _TIME_ALIASES[normalized]

    # 24h: 14:00, 14:00:00
    m24 = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", normalized)
    if m24:
        hour, minute = int(m24.group(1)), int(m24.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    # 12h: 2:00 pm, 2 pm, 10:30 am
    m12 = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", normalized)
    if m12:
        hour = int(m12.group(1))
        minute = int(m12.group(2) or 0)
        if m12.group(3) == "pm" and hour != 12:
            hour += 12
        elif m12.group(3) == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    return None


def format_slot_display(slot_time: time) -> str:
    """Consistent display: 9:00 AM, 2:00 PM (never use strftime lstrip)."""
    hour = slot_time.hour
    minute = slot_time.minute
    period = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {period}"


def format_slots_display(slots: list[time]) -> list[str]:
    return [format_slot_display(s) for s in slots]


def times_equal(a: time, b: time) -> bool:
    return (a.hour, a.minute) == (b.hour, b.minute)
