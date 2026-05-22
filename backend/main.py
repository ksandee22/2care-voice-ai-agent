import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.routes import router as api_router
from backend.api.websocket import router as ws_router
from backend.config import get_settings
from backend.controllers.pipeline import VoicePipeline
from memory.persistent_memory import PersistentMemory
from memory.session_memory import SessionMemory
from scheduler.campaign_scheduler import CampaignScheduler
from scheduler.database import init_db

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


async def _on_outbound_call(campaign):
    logging.getLogger(__name__).info(
        "Outbound campaign ready patient=%s type=%s",
        campaign.patient_id,
        campaign.campaign_type,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log = logging.getLogger(__name__)
    if settings.use_mock:
        log.info("AI mode: MOCK (no OpenAI calls). Set a valid OPENAI_API_KEY or MOCK_AI=false for production.")
    else:
        log.info("AI mode: OpenAI (STT + LLM + TTS)")
    session_memory = SessionMemory()
    persistent_memory = PersistentMemory()
    await session_memory.connect()
    await persistent_memory.connect()
    await init_db()

    from scheduler.database import get_session_factory
    from scheduler.appointment_engine import AppointmentEngine

    factory = get_session_factory()
    async with factory() as session:
        engine = AppointmentEngine(session)
        await engine.seed_if_empty()

    pipeline = VoicePipeline(session_memory, persistent_memory)
    campaign_scheduler = CampaignScheduler(on_outbound_call=_on_outbound_call)
    campaign_scheduler.start()

    app.state.session_memory = session_memory
    app.state.persistent_memory = persistent_memory
    app.state.pipeline = pipeline
    app.state.campaign_scheduler = campaign_scheduler

    yield

    campaign_scheduler.shutdown()
    await session_memory.close()
    await persistent_memory.close()


app = FastAPI(
    title="2Care.ai Voice AI Agent",
    description="Real-time multilingual clinical appointment voice assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)

frontend_path = ROOT / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


@app.get("/")
async def root():
    if frontend_path.exists():
        return RedirectResponse("/index.html")
    return {
        "status": "running",
        "docs": "/docs",
        "websocket": "/ws/voice",
    }
