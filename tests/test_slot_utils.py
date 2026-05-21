from datetime import time

from scheduler.slot_utils import format_slot_display, parse_time_slot


def test_parse_2_00_pm():
    assert parse_time_slot("2:00 PM") == time(14, 0)


def test_format_consistent():
    assert format_slot_display(time(9, 0)) == "9:00 AM"
    assert format_slot_display(time(10, 30)) == "10:30 AM"
    assert format_slot_display(time(14, 0)) == "2:00 PM"
    assert format_slot_display(time(16, 30)) == "4:30 PM"
