import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    app = websocket.app
    pipeline = app.state.pipeline

    session_id = websocket.query_params.get("session_id") or str(uuid.uuid4())
    patient_id = websocket.query_params.get("patient_id") or f"patient-{session_id[:8]}"
    outbound = websocket.query_params.get("outbound") == "true"
    campaign_message = websocket.query_params.get("campaign_message")

    if outbound and campaign_message:
        await app.state.session_memory.update(
            session_id,
            campaign_message=campaign_message,
            outbound_mode=True,
        )
        await websocket.send_json(
            {
                "type": "session",
                "session_id": session_id,
                "patient_id": patient_id,
                "outbound": True,
            }
        )
        greeting = await pipeline.process_text_turn(
            session_id,
            patient_id,
            "[OUTBOUND_START]",
            campaign_message=campaign_message,
        )
        await websocket.send_json({"type": "response", **greeting})
    else:
        await websocket.send_json(
            {
                "type": "session",
                "session_id": session_id,
                "patient_id": patient_id,
                "message": "Connected. Send audio or text.",
            }
        )

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get("type", "audio")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "text":
                result = await pipeline.process_text_turn(
                    session_id,
                    patient_id,
                    payload["text"],
                    payload.get("language"),
                )
                await websocket.send_json({"type": "response", **result})
                continue

            if msg_type == "audio":
                result = await pipeline.process_audio_turn(
                    session_id,
                    patient_id,
                    payload.get("audio_base64", ""),
                    payload.get("mime_type", "audio/webm"),
                    campaign_message=payload.get("campaign_message"),
                )
                await websocket.send_json({"type": "response", **result})
                continue

            await websocket.send_json({"type": "error", "message": f"Unknown type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected session=%s", session_id)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        msg = str(e)
        if "invalid_api_key" in msg or "Incorrect API key" in msg:
            msg = (
                "OpenAI API key is missing or invalid. On Render set MOCK_AI=true "
                "or add a real OPENAI_API_KEY from https://platform.openai.com/api-keys"
            )
        await websocket.send_json({"type": "error", "message": msg})
