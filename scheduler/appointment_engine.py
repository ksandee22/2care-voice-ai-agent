import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from scheduler.database import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorSchedule,
    Patient,
)
from scheduler.slot_utils import format_slots_display, parse_time_slot


SLOT_TIMES = [
    time(9, 0),
    time(10, 30),
    time(14, 0),
    time(16, 30),
]

DOCTORS_SEED = [
    ("dr-sharma", "Dr. Sharma", "cardiologist", "Apollo"),
    ("dr-patel", "Dr. Patel", "dermatologist", "Apollo"),
    ("dr-kumar", "Dr. Kumar", "general", "Fortis"),
    ("dr-iyer", "Dr. Iyer", "pediatrician", "Apollo"),
]


def parse_relative_date(text: str, base: Optional[date] = None) -> Optional[date]:
    base = base or date.today()
    t = (text or "").lower().strip()
    if t in ("today", "आज", "இன்று"):
        return base
    if t in ("tomorrow", "कल", "kal", "நாளை", "naalai"):
        return base + timedelta(days=1)
    if t in ("day after tomorrow",):
        return base + timedelta(days=2)
    try:
        return date.fromisoformat(t)
    except ValueError:
        return None


class AppointmentEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def seed_if_empty(self) -> None:
        result = await self.session.execute(select(Doctor).limit(1))
        if result.scalar_one_or_none():
            return

        for doc_id, name, specialty, hospital in DOCTORS_SEED:
            self.session.add(Doctor(id=doc_id, name=name, specialty=specialty, hospital=hospital))

        await self.session.flush()

        today = date.today()
        for offset in range(14):
            d = today + timedelta(days=offset)
            for doc_id, _, _, _ in DOCTORS_SEED:
                for slot in SLOT_TIMES:
                    self.session.add(
                        DoctorSchedule(
                            doctor_id=doc_id,
                            slot_date=d,
                            slot_time=slot,
                            is_available=True,
                        )
                    )
        await self.session.commit()

    async def find_doctor_by_specialty(self, specialty: str) -> Optional[Doctor]:
        q = specialty.lower().strip()
        result = await self.session.execute(
            select(Doctor).where(Doctor.specialty.ilike(f"%{q}%")).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_doctor(self, doctor_id: str) -> Optional[Doctor]:
        result = await self.session.execute(select(Doctor).where(Doctor.id == doctor_id))
        return result.scalar_one_or_none()

    async def check_availability(
        self,
        doctor_id: str,
        slot_date: date,
        slot_time: Optional[time] = None,
    ) -> list[time]:
        now = datetime.now()
        conditions = [
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.slot_date == slot_date,
            DoctorSchedule.is_available == True,  # noqa: E712
        ]
        if slot_time:
            conditions.append(DoctorSchedule.slot_time == slot_time)

        result = await self.session.execute(
            select(DoctorSchedule.slot_time).where(and_(*conditions)).order_by(DoctorSchedule.slot_time)
        )
        slots = [row[0] for row in result.all()]

        filtered = []
        for s in slots:
            slot_dt = datetime.combine(slot_date, s)
            if slot_dt > now:
                booked = await self._is_slot_booked(doctor_id, slot_date, s)
                if not booked:
                    filtered.append(s)
        return filtered

    async def get_alternative_slots(
        self,
        doctor_id: str,
        slot_date: date,
        exclude_time: Optional[time] = None,
    ) -> list[time]:
        """Free slots only; never includes booked slots or the rejected request time."""
        slots = await self.check_availability(doctor_id, slot_date)
        if exclude_time is not None:
            slots = [s for s in slots if (s.hour, s.minute) != (exclude_time.hour, exclude_time.minute)]
        return slots

    async def _is_slot_booked(self, doctor_id: str, slot_date: date, slot_time: time) -> bool:
        result = await self.session.execute(
            select(Appointment).where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == slot_date,
                Appointment.appointment_time == slot_time,
                Appointment.status == AppointmentStatus.SCHEDULED.value,
            )
        )
        return result.scalar_one_or_none() is not None

    async def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        slot_date: date,
        slot_time: time,
        notes: Optional[str] = None,
    ) -> dict:
        doctor = await self.get_doctor(doctor_id)
        if not doctor:
            return {"success": False, "error": "invalid_doctor", "message": "Doctor not found."}

        slot_dt = datetime.combine(slot_date, slot_time)
        if slot_dt <= datetime.now():
            return {"success": False, "error": "past_time", "message": "Cannot book appointments in the past."}

        if await self._is_slot_booked(doctor_id, slot_date, slot_time):
            alts = await self.get_alternative_slots(doctor_id, slot_date, exclude_time=slot_time)
            return {
                "success": False,
                "error": "conflict",
                "message": "That slot is already booked.",
                "requested_slot": format_slots_display([slot_time])[0],
                "alternatives": format_slots_display(alts),
            }

        available = await self.check_availability(doctor_id, slot_date, slot_time)
        if slot_time not in available:
            alts = await self.get_alternative_slots(doctor_id, slot_date, exclude_time=slot_time)
            return {
                "success": False,
                "error": "unavailable",
                "message": "Doctor is not available at that time.",
                "requested_slot": format_slots_display([slot_time])[0],
                "alternatives": format_slots_display(alts),
            }

        patient = await self.session.get(Patient, patient_id)
        if not patient:
            self.session.add(Patient(id=patient_id, name=f"Patient {patient_id[:8]}"))

        appt_id = str(uuid.uuid4())[:8]
        appt = Appointment(
            id=appt_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_date=slot_date,
            appointment_time=slot_time,
            status=AppointmentStatus.SCHEDULED.value,
            notes=notes,
        )
        self.session.add(appt)
        await self.session.commit()

        return {
            "success": True,
            "appointment_id": appt_id,
            "doctor": doctor.name,
            "specialty": doctor.specialty,
            "date": slot_date.isoformat(),
            "time": format_slots_display([slot_time])[0],
        }

    async def cancel_appointment(self, patient_id: str, appointment_id: Optional[str] = None) -> dict:
        if appointment_id:
            appt = await self.session.get(Appointment, appointment_id)
        else:
            result = await self.session.execute(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.status == AppointmentStatus.SCHEDULED.value,
                )
                .order_by(Appointment.appointment_date, Appointment.appointment_time)
                .limit(1)
            )
            appt = result.scalar_one_or_none()

        if not appt:
            return {"success": False, "error": "not_found", "message": "No active appointment found."}

        appt.status = AppointmentStatus.CANCELLED.value
        await self.session.commit()
        return {"success": True, "appointment_id": appt.id, "message": "Appointment cancelled."}

    async def reschedule_appointment(
        self,
        patient_id: str,
        new_date: date,
        new_time: time,
        appointment_id: Optional[str] = None,
    ) -> dict:
        if appointment_id:
            appt = await self.session.get(Appointment, appointment_id)
        else:
            result = await self.session.execute(
                select(Appointment)
                .where(
                    Appointment.patient_id == patient_id,
                    Appointment.status == AppointmentStatus.SCHEDULED.value,
                )
                .order_by(Appointment.appointment_date)
                .limit(1)
            )
            appt = result.scalar_one_or_none()

        if not appt or appt.status != AppointmentStatus.SCHEDULED.value:
            return {"success": False, "error": "not_found", "message": "No appointment to reschedule."}

        book_result = await self.book_appointment(
            patient_id, appt.doctor_id, new_date, new_time, notes="Rescheduled"
        )
        if not book_result.get("success"):
            return book_result

        appt.status = AppointmentStatus.CANCELLED.value
        await self.session.commit()
        book_result["previous_appointment_id"] = appt.id
        return book_result

    async def list_patient_appointments(self, patient_id: str) -> list[dict]:
        result = await self.session.execute(
            select(Appointment, Doctor)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status == AppointmentStatus.SCHEDULED.value,
            )
        )
        rows = []
        for appt, doctor in result.all():
            rows.append(
                {
                    "appointment_id": appt.id,
                    "doctor": doctor.name,
                    "specialty": doctor.specialty,
                    "date": appt.appointment_date.isoformat(),
                    "time": format_slots_display([appt.appointment_time])[0],
                }
            )
        return rows
