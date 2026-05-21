# 2Care.ai — Real-Time Multilingual Voice AI Agent

Clinical appointment booking system with **English, Hindi, and Tamil** voice support, contextual memory, outbound campaigns, and **latency measurement** (target: **&lt; 450 ms** from speech end to first audio).

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (optional — falls back to in-memory)
- OpenAI API key (optional — set `MOCK_AI=true` for demo without keys)

### Local Setup

```bash
cd voice-ai-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env: set OPENAI_API_KEY or MOCK_AI=true
```

Start Redis (optional):

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Run the server:

```bash
python run.py
```

Open **http://localhost:8000** for the voice demo UI, or **http://localhost:8000/docs** for API docs.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## Architecture

```
User Speech → WebSocket → STT → Language Detection → LLM Agent → Tools → Appointment DB
                                    ↓                      ↓
                              Session / Persistent Memory (Redis)
                                    ↓
                              TTS → Audio Response
```

See [docs/architecture.md](docs/architecture.md) and [docs/architecture-diagram.svg](docs/architecture-diagram.svg) (export to PNG/PDF for submission).

## Project Structure

```
voice-ai-agent/
├── backend/          # FastAPI, WebSocket, pipeline
├── agent/            # Prompts, LLM reasoning, tools
├── services/         # STT, TTS, language detection, latency
├── memory/           # Session + persistent Redis memory
├── scheduler/        # Appointment engine, campaigns, DB
├── frontend/         # Browser demo
├── tests/
└── docs/
```

## Features

| Feature | Implementation |
|---------|----------------|
| Book / reschedule / cancel | `AppointmentEngine` + agent tools |
| Conflict detection | Double-booking check + alternative slots |
| Multilingual | `langdetect` + Unicode heuristics; agent replies in detected language |
| Session memory | Redis `session:{id}` — messages, pending intent |
| Persistent memory | Redis `patient:{id}` — language, doctor, history |
| Outbound campaigns | `CampaignScheduler` + WebSocket `?outbound=true` |
| Latency logging | `services/latency.py` — per-stage + `first_audio_ms` in every response |

## API Examples

**Text turn (REST):**

```bash
curl -X POST http://localhost:8000/api/v1/conversation/text \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Book appointment with cardiologist tomorrow at 10:30 am\", \"patient_id\": \"p1\"}"
```

**WebSocket:**

```
ws://localhost:8000/ws/voice?patient_id=p1
{"type": "text", "text": "मुझे कल डॉक्टर से मिलना है"}
{"type": "audio", "audio_base64": "...", "mime_type": "audio/webm"}
```

**Outbound campaign:**

```
ws://localhost:8000/ws/voice?outbound=true&campaign_message=Hello, reminder for tomorrow...
```

## Memory Design

**Session** — current dialog, pending booking fields, campaign context (TTL 1 hour).

**Persistent** — `preferred_language`, `last_doctor`, `preferred_hospital`, `past_appointments` (TTL 30 days).

## Latency Breakdown

Every response includes:

```json
"latency": {
  "stt_ms": 120,
  "language_detection_ms": 2,
  "agent_ms": 180,
  "tools_ms": 15,
  "tts_ms": 95,
  "first_audio_ms": 412,
  "target_met": true
}
```

Server logs: `LATENCY {...}`.

### Trade-offs

- Mock mode (`MOCK_AI=true`): instant latency for demos; fixed sample transcripts.
- Production needs OpenAI + regional endpoints; streaming STT/TTS would improve sub-450ms consistency.
- SQLite by default; use PostgreSQL via `DATABASE_URL` for scale.

### Known Limitations

- No PSTN telephony integration (WebSocket simulates outbound calls).
- No barge-in / interrupt handling in v1.
- Tamil TTS uses general voices (OpenAI limitation).

## Testing

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

| Scenario | Command / Action |
|----------|-------------------|
| Book | Demo UI or POST `/api/v1/conversation/text` with book intent |
| Cancel | "Cancel my appointment" |
| Reschedule | Outbound demo → "Can we move it to Friday?" |
| Hindi | `मुझे कल डॉक्टर से मिलना है` |
| Conflict | Book same slot twice via API |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | STT, LLM, TTS |
| `MOCK_AI` | `true` = no OpenAI calls |
| `REDIS_URL` | Session + persistent memory |
| `DATABASE_URL` | Default SQLite in `./data/` |

## Deploy to Render (live public URL)

1. Push this repo to GitHub (see [DEPLOY.md](DEPLOY.md)).
2. On [Render](https://render.com) → **New +** → **Web Service** → connect the repo.
3. Use these settings:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/health`
4. Environment variables (Render dashboard):
   - `MOCK_AI` = `true` (demo without OpenAI billing), or set `OPENAI_API_KEY`
   - Optional: `REDIS_URL` (Redis add-on); app works without Redis (in-memory fallback)
5. After deploy, your links:
   - App demo: `https://YOUR-SERVICE.onrender.com/`
   - API docs: `https://YOUR-SERVICE.onrender.com/docs`
   - WebSocket: `wss://YOUR-SERVICE.onrender.com/ws/voice`

Or use the included `render.yaml` blueprint (**New +** → **Blueprint**).

## Submission Checklist

- [x] GitHub-ready project structure
- [x] README (setup, architecture, memory, latency, trade-offs)
- [x] Architecture diagram (`docs/architecture-diagram.svg`)
- [x] Render deployment config (`render.yaml`, `Procfile`)
- [ ] GitHub repo URL (push locally — see DEPLOY.md)
- [ ] Render live URL
- [ ] Loom video (≤ 3 min): demo + architecture walkthrough

## License

Assignment submission for 2Care.ai.
