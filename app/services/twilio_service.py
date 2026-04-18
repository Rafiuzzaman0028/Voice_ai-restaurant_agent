from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from app.core.logger import get_logger

logger = get_logger(__name__)

class TwilioService:
    @staticmethod
    def get_streaming_twiml(host: str, call_sid: str, caller_number: str) -> str:
        """
        Generates TwiML to connect the ongoing call to our WebSocket Media Stream.
        We pass call_sid and caller_number via custom stream parameters.
        """
        response = VoiceResponse()
        connect = Connect()
        
        # wss://host/ws/media
        ws_url = f"wss://{host}/ws/media"
        
        stream = Stream(url=ws_url)
        stream.parameter(name="callSid", value=call_sid)
        stream.parameter(name="callerNumber", value=caller_number)
        
        connect.append(stream)
        response.append(connect)
        
        # We can add a fallback or keep-alive pause if needed
        response.pause(length=120)
        
        logger.info(f"Generated TwiML for {call_sid} to connect to {ws_url}")
        
        return str(response)
