import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from backend.config import get_settings

logger = logging.getLogger(__name__)

_FALLBACK: dict[str, dict] = {}


class PersistentMemory:
    """Long-term patient preferences and history."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        try:
            self._client = redis.from_url(self.settings.redis_url, decode_responses=True)
            await self._client.ping()
            logger.info("Persistent memory connected to Redis")
        except Exception as e:
            logger.warning("Redis unavailable for persistent memory: %s", e)
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def _key(self, patient_id: str) -> str:
        return f"patient:{patient_id}"

    async def get(self, patient_id: str) -> dict[str, Any]:
        if self._client:
            raw = await self._client.get(self._key(patient_id))
            if raw:
                return json.loads(raw)
            return self._default_profile(patient_id)
        return _FALLBACK.get(patient_id, self._default_profile(patient_id))

    def _default_profile(self, patient_id: str) -> dict[str, Any]:
        return {
            "patient_id": patient_id,
            "preferred_language": None,
            "last_doctor": None,
            "preferred_hospital": None,
            "past_appointments": [],
            "interaction_count": 0,
        }

    async def set(self, patient_id: str, data: dict[str, Any]) -> None:
        if self._client:
            await self._client.setex(
                self._key(patient_id),
                self.settings.persistent_memory_ttl_seconds,
                json.dumps(data),
            )
        else:
            _FALLBACK[patient_id] = data

    async def record_interaction(
        self,
        patient_id: str,
        language: str,
        doctor: Optional[str] = None,
        hospital: Optional[str] = None,
        appointment_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        profile = await self.get(patient_id)
        profile["interaction_count"] = profile.get("interaction_count", 0) + 1
        if language:
            profile["preferred_language"] = language
        if doctor:
            profile["last_doctor"] = doctor
        if hospital:
            profile["preferred_hospital"] = hospital
        if appointment_summary:
            history = profile.get("past_appointments", [])
            history.append(appointment_summary)
            profile["past_appointments"] = history[-10:]
        await self.set(patient_id, profile)
        return profile
