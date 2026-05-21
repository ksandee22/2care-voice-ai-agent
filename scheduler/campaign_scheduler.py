import logging
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from scheduler.database import Appointment, AppointmentStatus, Campaign, get_session_factory
from scheduler.database import Doctor

logger = logging.getLogger(__name__)


class CampaignScheduler:
    """Background scheduler for outbound reminder campaigns."""

    def __init__(self, on_outbound_call: Optional[Callable] = None):
        self.scheduler = AsyncIOScheduler()
        self.on_outbound_call = on_outbound_call
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(self.process_pending_campaigns, "interval", seconds=30, id="campaigns")
        self.scheduler.add_job(self.generate_reminder_campaigns, "interval", hours=6, id="reminders")
        self.scheduler.start()
        self._started = True
        logger.info("Campaign scheduler started")

    def shutdown(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False

    async def generate_reminder_campaigns(self) -> None:
        """Create reminder campaigns for appointments in the next 24 hours."""
        from datetime import date

        tomorrow = date.today() + timedelta(days=1)
        factory = get_session_factory()

        async with factory() as session:
            result = await session.execute(
                select(Appointment, Doctor)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
                .where(
                    Appointment.appointment_date == tomorrow,
                    Appointment.status == AppointmentStatus.SCHEDULED.value,
                )
            )
            for appt, doctor in result.all():
                existing = await session.execute(
                    select(Campaign).where(
                        Campaign.patient_id == appt.patient_id,
                        Campaign.campaign_type == "appointment_reminder",
                        Campaign.status == "pending",
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                time_str = appt.appointment_time.strftime("%I:%M %p").lstrip("0")
                message = (
                    f"Hello, this is a reminder about your appointment with {doctor.name} "
                    f"tomorrow at {time_str}. Would you like to confirm, reschedule, or cancel?"
                )
                session.add(
                    Campaign(
                        id=str(uuid.uuid4())[:12],
                        patient_id=appt.patient_id,
                        campaign_type="appointment_reminder",
                        message=message,
                        scheduled_at=datetime.utcnow(),
                        status="pending",
                        metadata_json={
                            "appointment_id": appt.id,
                            "doctor": doctor.name,
                            "time": time_str,
                        },
                    )
                )
            await session.commit()

    async def process_pending_campaigns(self) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Campaign).where(Campaign.status == "pending").limit(10)
            )
            campaigns = result.scalars().all()
            for campaign in campaigns:
                if self.on_outbound_call:
                    await self.on_outbound_call(campaign)
                campaign.status = "completed"
            await session.commit()

    async def schedule_campaign(
        self,
        patient_id: str,
        campaign_type: str,
        message: str,
        run_at: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        factory = get_session_factory()
        campaign_id = str(uuid.uuid4())[:12]
        async with factory() as session:
            session.add(
                Campaign(
                    id=campaign_id,
                    patient_id=patient_id,
                    campaign_type=campaign_type,
                    message=message,
                    scheduled_at=run_at or datetime.utcnow(),
                    status="pending",
                    metadata_json=metadata,
                )
            )
            await session.commit()
        return campaign_id
