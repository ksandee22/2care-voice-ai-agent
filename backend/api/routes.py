import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from scheduler.campaign_scheduler import CampaignScheduler
from scheduler.database import get_session_factory
from scheduler.appointment_engine import AppointmentEngine

router = APIRouter()


class TextTurnRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    patient_id: Optional[str] = None
    language: Optional[str] = None


class BookRequest(BaseModel):
    patient_id: str
    specialty: str = "cardiologist"
    date: str = "tomorrow"
    time: str = "10:30 am"


class CampaignRequest(BaseModel):
    patient_id: str
    campaign_type: str = "appointment_reminder"
    message: str


@router.get("/health")
async def health():
    return {"status": "running", "service": "2care-voice-ai-agent"}


@router.post("/api/v1/conversation/text")
async def conversation_text(body: TextTurnRequest, request: Request):
    pipeline = request.app.state.pipeline
    session_id = body.session_id or str(uuid.uuid4())
    patient_id = body.patient_id or f"patient-{session_id[:8]}"
    result = await pipeline.process_text_turn(session_id, patient_id, body.text, body.language)
    result["session_id"] = session_id
    result["patient_id"] = patient_id
    return result


@router.post("/api/v1/appointments/book")
async def book_appointment(body: BookRequest):
    from agent.tools.appointments import AppointmentTools

    tools = AppointmentTools(body.patient_id)
    result = await tools.execute(
        "book_appointment",
        {"specialty": body.specialty, "date": body.date, "time": body.time},
    )
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result)
    return result


@router.get("/api/v1/appointments/{patient_id}")
async def list_appointments(patient_id: str):
    factory = get_session_factory()
    async with factory() as session:
        engine = AppointmentEngine(session)
        return {"appointments": await engine.list_patient_appointments(patient_id)}


@router.get("/api/v1/doctors")
async def list_doctors():
    from sqlalchemy import select
    from scheduler.database import Doctor

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(Doctor))
        doctors = result.scalars().all()
        return {
            "doctors": [
                {"id": d.id, "name": d.name, "specialty": d.specialty, "hospital": d.hospital}
                for d in doctors
            ]
        }


@router.post("/api/v1/campaigns")
async def create_campaign(body: CampaignRequest, request: Request):
    scheduler: CampaignScheduler = request.app.state.campaign_scheduler
    campaign_id = await scheduler.schedule_campaign(
        body.patient_id, body.campaign_type, body.message
    )
    return {"campaign_id": campaign_id, "status": "pending"}


@router.get("/api/v1/memory/session/{session_id}")
async def get_session_memory(session_id: str, request: Request):
    data = await request.app.state.session_memory.get(session_id)
    return data


@router.get("/api/v1/memory/patient/{patient_id}")
async def get_patient_memory(patient_id: str, request: Request):
    data = await request.app.state.persistent_memory.get(patient_id)
    return data
