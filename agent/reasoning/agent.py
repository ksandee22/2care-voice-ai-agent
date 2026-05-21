import json
import logging
import time
from typing import Any, Optional

from openai import AsyncOpenAI

from agent.prompt.system import LOCALIZED_FALLBACK, SYSTEM_PROMPT, TOOL_DEFINITIONS
from agent.tools.appointments import AppointmentTools
from backend.config import get_settings
from scheduler.slot_utils import parse_time_slot

logger = logging.getLogger(__name__)


class VoiceAgent:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        if not self.settings.use_mock:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def process(
        self,
        user_text: str,
        language: str,
        patient_id: str,
        session_context: dict[str, Any],
        patient_profile: dict[str, Any],
        campaign_message: Optional[str] = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        tools_total_ms = 0.0

        if self.settings.use_mock:
            return await self._mock_process(user_text, language, patient_id, start)

        messages = self._build_messages(
            user_text, language, session_context, patient_profile, campaign_message
        )

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=300,
            )
        except Exception as e:
            logger.exception("LLM failure: %s", e)
            return {
                "text": LOCALIZED_FALLBACK.get(language, LOCALIZED_FALLBACK["en"]),
                "agent_ms": (time.perf_counter() - start) * 1000,
                "tools_ms": 0,
                "tool_calls": [],
            }

        agent_ms = (time.perf_counter() - start) * 1000
        choice = response.choices[0]
        message = choice.message
        tool_calls_log = []

        if message.tool_calls:
            tool_handler = AppointmentTools(patient_id)
            messages.append(message.model_dump(exclude_none=True))

            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                tool_start = time.perf_counter()
                result = await tool_handler.execute(tc.function.name, args)
                tools_total_ms += (time.perf_counter() - tool_start) * 1000
                tool_calls_log.append({"name": tc.function.name, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

            follow_start = time.perf_counter()
            follow = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                max_tokens=300,
            )
            agent_ms += (time.perf_counter() - follow_start) * 1000
            reply = follow.choices[0].message.content or ""
        else:
            reply = message.content or LOCALIZED_FALLBACK.get(language, LOCALIZED_FALLBACK["en"])

        pending = self._extract_pending_context(user_text, reply, tool_calls_log, session_context)

        return {
            "text": reply.strip(),
            "agent_ms": agent_ms,
            "tools_ms": tools_total_ms,
            "tool_calls": tool_calls_log,
            "pending_context": pending,
        }

    def _build_messages(
        self,
        user_text: str,
        language: str,
        session_context: dict,
        patient_profile: dict,
        campaign_message: Optional[str],
    ) -> list[dict]:
        lang_name = {"en": "English", "hi": "Hindi", "ta": "Tamil"}.get(language, "English")
        context_parts = [
            f"Respond in {lang_name}.",
            f"Session state: {json.dumps(session_context.get('pending', {}))}",
            f"Patient profile: {json.dumps({k: patient_profile.get(k) for k in ('preferred_language', 'last_doctor', 'preferred_hospital', 'past_appointments')})}",
        ]
        if campaign_message:
            context_parts.append(f"OUTBOUND CAMPAIGN — open with: {campaign_message}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "\n".join(context_parts)},
        ]

        for msg in session_context.get("messages", [])[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_text})
        return messages

    def _extract_pending_context(
        self,
        user_text: str,
        reply: str,
        tool_calls: list,
        session_context: dict,
    ) -> dict:
        pending = dict(session_context.get("pending", {}))
        lower = user_text.lower()

        if any(w in lower for w in ("book", "appointment", "बुक", "புக்", "மருத்துவ")):
            pending["intent"] = "booking"
        elif any(w in lower for w in ("cancel", "रद्द", "ரத்து")):
            pending["intent"] = "cancel"
        elif any(w in lower for w in ("reschedule", "move", "बदल", "மாற்ற")):
            pending["intent"] = "reschedule"

        for tc in tool_calls:
            if tc["name"] == "book_appointment" and tc["result"].get("success"):
                pending.clear()
            elif tc["name"] == "check_availability":
                pending["awaiting"] = "time_selection"

        pending["last_agent_reply"] = reply[:200]
        return pending

    async def _mock_process(
        self, user_text: str, language: str, patient_id: str, start: float
    ) -> dict:
        tools = AppointmentTools(patient_id)
        lower = user_text.lower()

        if "cancel" in lower or "रद्द" in user_text:
            result = await tools.execute("cancel_appointment", {})
            if result.get("success"):
                text = {
                    "en": "Your appointment has been cancelled.",
                    "hi": "आपकी अपॉइंटमेंट रद्द कर दी गई है।",
                    "ta": "உங்கள் சந்திப்பு ரத்து செய்யப்பட்டது.",
                }.get(language, "Appointment cancelled.")
            else:
                text = result.get("message", "No appointment found.")
        elif "reschedule" in lower or "friday" in lower or "शुक्र" in user_text:
            result = await tools.execute(
                "reschedule_appointment",
                {"date": "tomorrow" if "tomorrow" in lower else "tomorrow", "time": "2 pm"},
            )
            if result.get("success"):
                text = {
                    "en": f"Rescheduled with {result.get('doctor')} on {result.get('date')} at {result.get('time')}.",
                    "hi": f"अपॉइंटमेंट {result.get('date')} को {result.get('time')} बजे तय हो गई।",
                    "ta": f"சந்திப்பு {result.get('date')} {result.get('time')}க்கு மாற்றப்பட்டது.",
                }.get(language, "Rescheduled.")
            else:
                alts = result.get("alternatives", [])
                text = result.get("message", "Could not reschedule.") + (
                    f" Available: {', '.join(alts)}" if alts else ""
                )
        elif "availability" in lower or "available" in lower:
            result = await tools.execute(
                "check_availability",
                {"specialty": "cardiologist", "date": "tomorrow"},
            )
            slots = ", ".join(result.get("available_slots", [])[:4])
            text = {"en": f"Available slots: {slots}.", "hi": f"उपलब्ध समय: {slots}.", "ta": f"கிடைக்கும் நேரம்: {slots}."}.get(
                language, f"Slots: {slots}"
            )
        else:
            book_args = {"specialty": "cardiologist", "date": "tomorrow", "time": "10:30 am"}
            if "tomorrow" not in lower and ("today" in lower or "आज" in user_text):
                book_args["date"] = "today"
            parsed_time = parse_time_slot(user_text)
            if not parsed_time:
                import re

                m = re.search(
                    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})",
                    user_text,
                    re.IGNORECASE,
                )
                if m:
                    parsed_time = parse_time_slot(m.group(1))
            if parsed_time:
                from scheduler.slot_utils import format_slot_display

                book_args["time"] = format_slot_display(parsed_time)
            result = await tools.execute("book_appointment", book_args)
            if result.get("success"):
                text = {
                    "en": f"Booked with {result['doctor']} on {result['date']} at {result['time']}.",
                    "hi": f"{result['doctor']} के साथ {result['date']} को {result['time']} बजे बुक हो गया।",
                    "ta": f"{result['doctor']} உடன் {result['date']} {result['time']}க்கு பதிவு செய்யப்பட்டது.",
                }.get(language, "Booked.")
            else:
                alts = result.get("alternatives", [])
                msg = result.get("message") or "Could not book."
                if result.get("error") == "conflict":
                    msg = "That slot is already booked."
                text = msg + (f" Try: {', '.join(alts)}" if alts else "")

        return {
            "text": text,
            "agent_ms": (time.perf_counter() - start) * 1000,
            "tools_ms": result.get("tool_duration_ms", 0),
            "tool_calls": [{"name": "mock", "result": result}],
            "pending_context": {},
        }
