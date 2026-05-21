import json
import time
from datetime import date
from typing import Any, Optional

from scheduler.appointment_engine import AppointmentEngine, parse_relative_date
from scheduler.slot_utils import format_slots_display, parse_time_slot
from scheduler.database import get_session_factory


class AppointmentTools:
    def __init__(self, patient_id: str):
        self.patient_id = patient_id

    async def _engine(self) -> AppointmentEngine:
        factory = get_session_factory()
        session = factory()
        engine = AppointmentEngine(session)
        await engine.seed_if_empty()
        return engine

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        factory = get_session_factory()
        async with factory() as session:
            engine = AppointmentEngine(session)
            await engine.seed_if_empty()

            if name == "check_availability":
                result = await self._check_availability(engine, arguments)
            elif name == "book_appointment":
                result = await self._book(engine, arguments)
            elif name == "cancel_appointment":
                result = await engine.cancel_appointment(
                    self.patient_id, arguments.get("appointment_id")
                )
            elif name == "reschedule_appointment":
                result = await self._reschedule(engine, arguments)
            elif name == "list_appointments":
                appts = await engine.list_patient_appointments(self.patient_id)
                result = {"success": True, "appointments": appts}
            else:
                result = {"success": False, "error": "unknown_tool"}

        result["tool_duration_ms"] = (time.perf_counter() - start) * 1000
        return result

    async def _resolve_doctor(self, engine: AppointmentEngine, args: dict) -> Optional[str]:
        if args.get("doctor_id"):
            doc = await engine.get_doctor(args["doctor_id"])
            return doc.id if doc else None
        specialty = args.get("specialty")
        if specialty:
            doc = await engine.find_doctor_by_specialty(specialty)
            return doc.id if doc else None
        return None

    async def _check_availability(self, engine: AppointmentEngine, args: dict) -> dict:
        doctor_id = await self._resolve_doctor(engine, args)
        if not doctor_id:
            return {"success": False, "error": "doctor_not_found", "message": "Doctor not found."}

        slot_date = parse_relative_date(args.get("date", "tomorrow"))
        if not slot_date:
            return {"success": False, "error": "invalid_date"}

        slots = await engine.check_availability(doctor_id, slot_date)
        doctor = await engine.get_doctor(doctor_id)
        return {
            "success": True,
            "doctor": doctor.name if doctor else doctor_id,
            "date": slot_date.isoformat(),
            "available_slots": format_slots_display(slots),
        }

    async def _book(self, engine: AppointmentEngine, args: dict) -> dict:
        doctor_id = await self._resolve_doctor(engine, args)
        if not doctor_id:
            return {"success": False, "error": "doctor_not_found", "message": "Which doctor or specialty?"}

        slot_date = parse_relative_date(args.get("date", "tomorrow"))
        slot_time = parse_time_slot(args.get("time", ""))
        if not slot_date:
            return {"success": False, "error": "invalid_date", "message": "Please specify a date."}
        if not slot_time:
            slots = await engine.check_availability(doctor_id, slot_date)
            return {
                "success": False,
                "error": "need_time",
                "message": "Please choose a time slot.",
                "available_slots": format_slots_display(slots),
            }

        return await engine.book_appointment(self.patient_id, doctor_id, slot_date, slot_time)

    async def _reschedule(self, engine: AppointmentEngine, args: dict) -> dict:
        slot_date = parse_relative_date(args.get("date", ""))
        slot_time = parse_time_slot(args.get("time", ""))
        if not slot_date or not slot_time:
            return {"success": False, "error": "invalid_slot"}
        return await engine.reschedule_appointment(
            self.patient_id,
            slot_date,
            slot_time,
            args.get("appointment_id"),
        )
