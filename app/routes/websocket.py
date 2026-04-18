import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.logger import get_logger
from app.core.orchestrator import CallOrchestrator

logger = get_logger(__name__)
router = APIRouter()

@router.websocket("/ws/media")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # We will instantiate the Orchestrator after the first 'start' message
    orchestrator = None
    session_id = str(uuid.uuid4())
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")
            
            if event == "start":
                # Twilio's start event includes custom parameters defined in our TwiML
                call_sid = data["start"]["customParameters"].get("callSid", "UnknownSID")
                caller_number = data["start"]["customParameters"].get("callerNumber", "UnknownNumber")
                
                logger.info(f"WebSocket Connected - Session: {session_id}, Call: {call_sid}")
                
                orchestrator = CallOrchestrator(
                    websocket=websocket,
                    session_id=session_id,
                    caller_number=caller_number,
                    call_sid=call_sid
                )
                await orchestrator.start()
                await orchestrator.handle_twilio_message(message)
                
            elif event in ["media", "stop"]:
                if orchestrator:
                    await orchestrator.handle_twilio_message(message)
                    
                if event == "stop":
                    # Stop message means Twilio is ending the stream
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket Client Disconnected - Session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        if orchestrator:
            await orchestrator.stop()
