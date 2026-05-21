import base64
import logging
import time
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)

VOICE_BY_LANG = {
    "en": "alloy",
    "hi": "nova",
    "ta": "nova",
}


@dataclass
class TTSResult:
    audio_base64: str
    mime_type: str
    duration_ms: float


class TextToSpeechService:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        if not self.settings.use_mock:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def synthesize(self, text: str, language: str = "en") -> TTSResult:
        start = time.perf_counter()

        if self.settings.use_mock:
            duration_ms = (time.perf_counter() - start) * 1000
            return TTSResult(audio_base64="", mime_type="audio/mpeg", duration_ms=duration_ms)

        voice = VOICE_BY_LANG.get(language, "alloy")
        response = await self._client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )

        audio_bytes = response.content
        duration_ms = (time.perf_counter() - start) * 1000

        return TTSResult(
            audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
            mime_type="audio/mpeg",
            duration_ms=duration_ms,
        )
