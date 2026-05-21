import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    session_id: str
    speech_end_ts: float = 0.0
    stt_ms: float = 0.0
    language_detection_ms: float = 0.0
    agent_ms: float = 0.0
    tools_ms: float = 0.0
    tts_ms: float = 0.0
    total_ms: float = 0.0
    first_audio_ms: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)

    def log(self) -> dict[str, Any]:
        payload = {
            "session_id": self.session_id,
            "stt_ms": round(self.stt_ms, 2),
            "language_detection_ms": round(self.language_detection_ms, 2),
            "agent_ms": round(self.agent_ms, 2),
            "tools_ms": round(self.tools_ms, 2),
            "tts_ms": round(self.tts_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "first_audio_ms": round(self.first_audio_ms, 2),
            "target_met": self.first_audio_ms < 450,
            "stages": {k: round(v, 2) for k, v in self.stages.items()},
        }
        logger.info("LATENCY %s", payload)
        return payload


class LatencyTracker:
    def __init__(self, session_id: str):
        self.metrics = LatencyMetrics(session_id=session_id)
        self._marks: dict[str, float] = {}

    def mark_speech_end(self) -> None:
        self.metrics.speech_end_ts = time.perf_counter()

    def start(self, stage: str) -> None:
        self._marks[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        if stage not in self._marks:
            return 0.0
        elapsed = (time.perf_counter() - self._marks[stage]) * 1000
        self.metrics.stages[stage] = elapsed
        setattr(self.metrics, f"{stage}_ms", elapsed) if hasattr(self.metrics, f"{stage}_ms") else None
        return elapsed

    def record_stage(self, stage: str, ms: float) -> None:
        self.metrics.stages[stage] = ms
        mapping = {
            "stt": "stt_ms",
            "language_detection": "language_detection_ms",
            "agent": "agent_ms",
            "tools": "tools_ms",
            "tts": "tts_ms",
        }
        attr = mapping.get(stage)
        if attr:
            setattr(self.metrics, attr, ms)

    def finalize_first_audio(self) -> dict[str, Any]:
        if self.metrics.speech_end_ts:
            self.metrics.first_audio_ms = (time.perf_counter() - self.metrics.speech_end_ts) * 1000
            self.metrics.total_ms = self.metrics.first_audio_ms
        return self.metrics.log()
