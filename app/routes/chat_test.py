from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.state_manager import StateManager
from app.services.openai_service import OpenAIService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    session_id: str
    message: str

@router.post("/test/chat")
async def test_chat(request: ChatRequest):
    """
    Simulates a user message via Swagger UI bypassing Twilio media streams.
    """
    # Create or get session (caller_number and call_sid are mocked)
    state = StateManager.get_or_create_session(
        session_id=request.session_id,
        caller_number="+10000000000",
        call_sid=f"test_{request.session_id}"
    )
    
    try:
        ai_reply = await OpenAIService.get_response(request.message, state)
        
        # Save updated memory to Redis
        StateManager.save_session(request.session_id, state)
        
        return {
            "session_id": request.session_id,
            "user_message": request.message,
            "ai_reply": ai_reply,
            "order_stage": state.stage,
            "is_confirmed": state.confirmation_status
        }
    except Exception as e:
        logger.error(f"Error in test chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
