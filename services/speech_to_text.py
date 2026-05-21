import base64
import io
import logging
import time
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class STTResult:
    text: str
    language: Optional[str]
    duration_ms: float


class SpeechToTextService:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        if not self.settings.use_mock:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> STTResult:
        start = time.perf_counter()

        if self.settings.use_mock:
            text = "book appointment with cardiologist tomorrow"
            duration_ms = (time.perf_counter() - start) * 1000
            return STTResult(text=text, language="en", duration_ms=duration_ms)

        ext = "webm"
        if "wav" in mime_type:
            ext = "wav"
        elif "mp3" in mime_type or "mpeg" in mime_type:
            ext = "mp3"

        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = f"audio.{ext}"

        response = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
            response_format="verbose_json",
        )

        duration_ms = (time.perf_counter() - start) * 1000
        text = getattr(response, "text", "") or ""
        language = getattr(response, "language", None)

        return STTResult(text=text.strip(), language=language, duration_ms=duration_ms)

    async def transcribe_base64(self, audio_b64: str, mime_type: str = "audio/webm") -> STTResult:
        audio_bytes = base64.b64decode(audio_b64)
        return await self.transcribe(audio_bytes, mime_type)
