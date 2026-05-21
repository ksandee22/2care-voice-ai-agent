import logging
from typing import Any, Optional

from agent.reasoning.agent import VoiceAgent
from memory.persistent_memory import PersistentMemory
from memory.session_memory import SessionMemory
from services.language_detection import LanguageDetectionService
from services.latency import LatencyTracker
from services.speech_to_text import SpeechToTextService
from services.text_to_speech import TextToSpeechService

logger = logging.getLogger(__name__)


class VoicePipeline:
    """End-to-end: audio → STT → language → agent → TTS with latency tracking."""

    def __init__(
        self,
        session_memory: SessionMemory,
        persistent_memory: PersistentMemory,
    ):
        self.session_memory = session_memory
        self.persistent_memory = persistent_memory
        self.stt = SpeechToTextService()
        self.tts = TextToSpeechService()
        self.lang = LanguageDetectionService()
        self.agent = VoiceAgent()

    async def process_audio_turn(
        self,
        session_id: str,
        patient_id: str,
        audio_b64: str,
        mime_type: str = "audio/webm",
        campaign_message: Optional[str] = None,
    ) -> dict[str, Any]:
        tracker = LatencyTracker(session_id)
        tracker.mark_speech_end()

        stt_result = await self.stt.transcribe_base64(audio_b64, mime_type)
        tracker.record_stage("stt", stt_result.duration_ms)

        tracker.start("language_detection")
        language = self.lang.detect(stt_result.text)
        if stt_result.language:
            language = self.lang.normalize(stt_result.language[:2])
        tracker.end("language_detection")

        session_state = await self.session_memory.get(session_id)
        profile = await self.persistent_memory.get(patient_id)
        if profile.get("preferred_language") and not stt_result.text:
            language = profile["preferred_language"]

        await self.session_memory.append_message(session_id, "user", stt_result.text)

        tracker.start("agent")
        agent_result = await self.agent.process(
            user_text=stt_result.text,
            language=language,
            patient_id=patient_id,
            session_context=session_state,
            patient_profile=profile,
            campaign_message=campaign_message or session_state.get("campaign_message"),
        )
        tracker.record_stage("agent", agent_result.get("agent_ms", 0))
        tracker.record_stage("tools", agent_result.get("tools_ms", 0))

        reply_text = agent_result["text"]
        await self.session_memory.append_message(session_id, "assistant", reply_text)

        pending = agent_result.get("pending_context", {})
        await self.session_memory.update(
            session_id,
            pending=pending,
            last_language=language,
            last_transcript=stt_result.text,
        )

        for tc in agent_result.get("tool_calls", []):
            res = tc.get("result", {})
            if res.get("success") and "doctor" in res:
                await self.persistent_memory.record_interaction(
                    patient_id,
                    language=language,
                    doctor=res.get("doctor"),
                    appointment_summary=f"{res.get('date')} {res.get('time')} with {res.get('doctor')}",
                )

        await self.persistent_memory.record_interaction(patient_id, language=language)

        tts_result = await self.tts.synthesize(reply_text, language)
        tracker.record_stage("tts", tts_result.duration_ms)

        latency = tracker.finalize_first_audio()

        return {
            "transcript": stt_result.text,
            "language": language,
            "language_name": self.lang.display_name(language),
            "response_text": reply_text,
            "audio_base64": tts_result.audio_base64,
            "audio_mime": tts_result.mime_type,
            "latency": latency,
            "tool_calls": agent_result.get("tool_calls", []),
        }

    async def process_text_turn(
        self,
        session_id: str,
        patient_id: str,
        text: str,
        language: Optional[str] = None,
        campaign_message: Optional[str] = None,
        synthesize: bool = True,
    ) -> dict[str, Any]:
        tracker = LatencyTracker(session_id)
        tracker.mark_speech_end()

        tracker.record_stage("stt", 0)
        lang = language or self.lang.detect(text)
        tracker.record_stage("language_detection", 1)

        session_state = await self.session_memory.get(session_id)
        profile = await self.persistent_memory.get(patient_id)

        await self.session_memory.append_message(session_id, "user", text)

        agent_result = await self.agent.process(
            user_text=text,
            language=lang,
            patient_id=patient_id,
            session_context=session_state,
            patient_profile=profile,
            campaign_message=campaign_message,
        )
        tracker.record_stage("agent", agent_result.get("agent_ms", 0))
        tracker.record_stage("tools", agent_result.get("tools_ms", 0))

        reply_text = agent_result["text"]
        await self.session_memory.append_message(session_id, "assistant", reply_text)
        await self.session_memory.update(session_id, pending=agent_result.get("pending_context", {}))

        audio_b64 = ""
        tts_ms = 0.0
        if synthesize:
            tts_result = await self.tts.synthesize(reply_text, lang)
            audio_b64 = tts_result.audio_base64
            tts_ms = tts_result.duration_ms
        tracker.record_stage("tts", tts_ms)

        latency = tracker.finalize_first_audio()

        return {
            "transcript": text,
            "language": lang,
            "response_text": reply_text,
            "audio_base64": audio_b64,
            "audio_mime": "audio/mpeg",
            "latency": latency,
        }
