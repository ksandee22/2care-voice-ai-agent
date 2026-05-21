import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from backend.config import get_settings

logger = logging.getLogger(__name__)

_FALLBACK: dict[str, dict] = {}


class SessionMemory:
    """Redis-backed session context with in-memory fallback."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        try:
            self._client = redis.from_url(self.settings.redis_url, decode_responses=True)
            await self._client.ping()
            logger.info("Session memory connected to Redis")
        except Exception as e:
            logger.warning("Redis unavailable for session memory: %s", e)
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get(self, session_id: str) -> dict[str, Any]:
        if self._client:
            raw = await self._client.get(self._key(session_id))
            if raw:
                return json.loads(raw)
            return {}
        return _FALLBACK.get(session_id, {})

    async def set(self, session_id: str, data: dict[str, Any]) -> None:
        if self._client:
            await self._client.setex(
                self._key(session_id),
                self.settings.session_ttl_seconds,
                json.dumps(data),
            )
        else:
            _FALLBACK[session_id] = data

    async def update(self, session_id: str, **fields: Any) -> dict[str, Any]:
        current = await self.get(session_id)
        current.update(fields)
        await self.set(session_id, current)
        return current

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        state = await self.get(session_id)
        messages = state.get("messages", [])
        messages.append({"role": role, "content": content})
        if len(messages) > 20:
            messages = messages[-20:]
        state["messages"] = messages
        await self.set(session_id, state)

    async def clear(self, session_id: str) -> None:
        if self._client:
            await self._client.delete(self._key(session_id))
        _FALLBACK.pop(session_id, None)
