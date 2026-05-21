from datetime import date, datetime, time
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Time, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    specialty: Mapped[str] = mapped_column(String(64), index=True)
    hospital: Mapped[str] = mapped_column(String(128), default="Apollo")


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedule"
    __table_args__ = (UniqueConstraint("doctor_id", "slot_date", "slot_time", name="uq_doctor_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), index=True)
    slot_date: Mapped[date] = mapped_column(Date, index=True)
    slot_time: Mapped[time] = mapped_column(Time)
    is_available: Mapped[bool] = mapped_column(default=True)

    doctor: Mapped["Doctor"] = relationship()


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="Patient")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), index=True)
    appointment_date: Mapped[date] = mapped_column(Date, index=True)
    appointment_time: Mapped[time] = mapped_column(Time)
    status: Mapped[str] = mapped_column(String(32), default=AppointmentStatus.SCHEDULED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    doctor: Mapped["Doctor"] = relationship()
    patient: Mapped["Patient"] = relationship()


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    campaign_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(512))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    import os

    os.makedirs("data", exist_ok=True)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
