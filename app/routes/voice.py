from fastapi import APIRouter, Request
from fastapi.responses import Response
from app.services.twilio_service import TwilioService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("/voice")
async def handle_incoming_call(request: Request):
    """
    Twilio Webhook endpoint. Twilio sends a POST request here when a call connects.
    We return TwiML `<Connect><Stream>` to establish the websocket stream.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid", "UnknownSID")
    caller_number = form_data.get("From", "UnknownNumber")
    
    logger.info(f"Incoming call from: {caller_number} (SID: {call_sid})")

    # In a real environment, you extract your ngrok domain dynamically or from env
    # Using the host header allows us to not hardcode the Ngrok URL
    host = request.headers.get("host")
    
    # Generate TwiML
    twiml_response = TwilioService.get_streaming_twiml(
        host=host, 
        call_sid=call_sid, 
        caller_number=caller_number
    )
    
    return Response(content=twiml_response, media_type="application/xml")
