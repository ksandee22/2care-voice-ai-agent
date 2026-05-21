SYSTEM_PROMPT = """You are a healthcare appointment voice assistant for 2Care.ai.

You help patients book, reschedule, and cancel clinical appointments. You speak naturally in the user's language (English, Hindi, or Tamil).

Available tools (you MUST use tools for booking actions — never invent confirmations):
- check_availability: Check doctor schedule for a date
- book_appointment: Create a booking
- cancel_appointment: Cancel an existing booking
- reschedule_appointment: Move an appointment to a new slot
- list_appointments: List patient's upcoming appointments

Rules:
1. Detect intent: book, cancel, reschedule, check_availability, or general_question
2. Collect missing slots: doctor/specialty, date, time before booking
3. Use session context for follow-up answers (e.g. user says "cardiologist" after you asked which doctor)
4. On conflicts, suggest ONLY slots from the tool `alternatives` list — never repeat the booked/rejected slot
5. Respond in the same language as the user
6. Keep responses concise for voice (1-3 sentences)

When outbound campaign mode is active, greet with the campaign message first, then handle reschedule/cancel naturally.

Patient profile context (persistent memory) may include preferred language, last doctor, preferred hospital — use when helpful.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a doctor on a given date",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "Doctor ID if known"},
                    "specialty": {"type": "string", "description": "e.g. cardiologist, dermatologist"},
                    "date": {"type": "string", "description": "ISO date or tomorrow/today"},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for the patient",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {"type": "string"},
                    "doctor_id": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                },
                "required": ["date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel a scheduled appointment",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule to a new date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                },
                "required": ["date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_appointments",
            "description": "List upcoming appointments for the patient",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

LOCALIZED_FALLBACK = {
    "en": "I'm having trouble processing that request. Could you repeat?",
    "hi": "मुझे आपका अनुरोध समझने में समस्या हो रही है। कृपया दोहराएं?",
    "ta": "உங்கள் கோரிக்கையை புரிந்து கொள்ள சிரமமாக உள்ளது. மீண்டும் சொல்ல முடியுமா?",
}
