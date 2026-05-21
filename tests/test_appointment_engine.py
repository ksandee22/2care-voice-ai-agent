import asyncio
import os
import sys
from datetime import date, time, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["MOCK_AI"] = "true"

from scheduler.database import init_db, get_session_factory, Appointment, AppointmentStatus
from scheduler.appointment_engine import AppointmentEngine, parse_relative_date
from scheduler.slot_utils import format_slot_display, parse_time_slot
from sqlalchemy import select


@pytest.fixture
async def engine():
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        appt_engine = AppointmentEngine(session)
        await appt_engine.seed_if_empty()
        yield appt_engine, session


@pytest.mark.asyncio
async def test_parse_relative_date():
    assert parse_relative_date("tomorrow") == date.today() + timedelta(days=1)
    assert parse_relative_date("कल") == date.today() + timedelta(days=1)


@pytest.mark.asyncio
async def test_book_and_conflict(engine):
    appt_engine, session = engine
    patient_id = "test-patient-1"
    doctor = await appt_engine.find_doctor_by_specialty("cardiologist")
    assert doctor is not None
    slot_date = date.today() + timedelta(days=1)
    slot_time = time(10, 30)

    first = await appt_engine.book_appointment(patient_id, doctor.id, slot_date, slot_time)
    assert first["success"] is True

    second = await appt_engine.book_appointment(patient_id, doctor.id, slot_date, slot_time)
    assert second["success"] is False
    assert second["error"] == "conflict"
    assert "alternatives" in second


@pytest.mark.asyncio
async def test_cancel_appointment(engine):
    appt_engine, session = engine
    patient_id = "test-patient-2"
    doctor = await appt_engine.find_doctor_by_specialty("dermatologist")
    slot_date = date.today() + timedelta(days=2)
    booked = await appt_engine.book_appointment(patient_id, doctor.id, slot_date, time(14, 0))
    assert booked["success"]

    cancelled = await appt_engine.cancel_appointment(patient_id, booked["appointment_id"])
    assert cancelled["success"]


@pytest.mark.asyncio
async def test_parse_time_slot_variants():
    assert parse_time_slot("2:00 PM") == time(14, 0)
    assert parse_time_slot("2:00pm") == time(14, 0)
    assert parse_time_slot("2 pm") == time(14, 0)
    assert format_slot_display(time(14, 0)) == "2:00 PM"


@pytest.mark.asyncio
async def test_conflict_alternatives_exclude_booked_slot(engine):
    appt_engine, _ = engine
    doctor = await appt_engine.find_doctor_by_specialty("cardiologist")
    slot_date = date.today() + timedelta(days=1)
    slot_time = time(14, 0)

    first = await appt_engine.book_appointment("patient-a", doctor.id, slot_date, slot_time)
    assert first["success"]

    second = await appt_engine.book_appointment("patient-b", doctor.id, slot_date, slot_time)
    assert second["success"] is False
    assert second["error"] == "conflict"
    assert "2:00 PM" not in second["alternatives"]
    assert format_slot_display(slot_time) not in second["alternatives"]


@pytest.mark.asyncio
async def test_past_booking_rejected(engine):
    appt_engine, _ = engine
    doctor = await appt_engine.find_doctor_by_specialty("general")
    yesterday = date.today() - timedelta(days=1)
    result = await appt_engine.book_appointment(
        "p3", doctor.id, yesterday, time(9, 0)
    )
    assert result["success"] is False
    assert result["error"] == "past_time"
