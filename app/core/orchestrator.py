import json
from app.core.logger import get_logger
from app.core.state_manager import StateManager
from app.services.deepgram_service import DeepgramService
from app.services.openai_service import OpenAIService
from app.services.elevenlabs_service import ElevenLabsService

logger = get_logger(__name__)

class CallOrchestrator:
    def __init__(self, websocket, session_id: str, caller_number: str, call_sid: str):
        self.twilio_ws = websocket
        self.session_id = session_id
        self.state = StateManager.get_or_create_session(session_id, caller_number, call_sid)
        
        # Stream identifier provided by Twilio stream start event
        self.stream_sid = None
        
        self.deepgram = DeepgramService(self.on_transcript_received, interim_callback=self.on_user_speaking)
        self.elevenlabs = ElevenLabsService(self.on_audio_received)
        
        # Guard to prevent AI from overlapping responses
        self.is_processing_ai = False
        self.active_ai_task = None

    async def start(self):
        logger.info(f"Orchestrator starting for session: {self.session_id}")
        await self.deepgram.connect()
        
        # Initial greeting from the AI to kick off the call
        await self.trigger_ai_response("Hello.")

    async def handle_twilio_message(self, message: str):
        try:
            data = json.loads(message)
            event = data.get("event")
            
            if event == "start":
                self.stream_sid = data["start"]["streamSid"]
                logger.info(f"Twilio Media Stream started: {self.stream_sid}")
                
            elif event == "media":
                # Twilio sends base64 mulaw payload
                import base64
                audio_payload = data["media"]["payload"]
                audio_bytes = base64.b64decode(audio_payload)
                
                # Send bytes to Deepgram continuously (Twilio echo cancellation prevents looping)
                await self.deepgram.send_audio(audio_bytes)
                    
            elif event == "stop":
                logger.info(f"Twilio Media Stream stopped: {self.stream_sid}")
                await self.stop()
                
        except Exception as e:
            logger.error(f"Error handling Twilio message: {e}")

    async def on_transcript_received(self, text: str):
        logger.info(f"Caller Said: {text}")
        
        # If AI is generating, cancel it and restart with the new final speech
        if self.active_ai_task and not self.active_ai_task.done():
            self.active_ai_task.cancel()
            
        import asyncio
        self.active_ai_task = asyncio.create_task(self.trigger_ai_response(text))

    async def on_user_speaking(self, transcript: str = ""):
        """
        Fired the instant the user starts forming their first word of a sentence.
        We quietly hide the ElevenLabs connection delay behind their voice.
        """
        # Guard against zero-length or 1-character phantom noise ticks
        if len(transcript.strip()) < 3:
            return
            
        # 1. Stop Twilio from playing whatever audio it has buffered (Barge-In)
        if self.twilio_ws and self.stream_sid:
            try:
                clear_message = {
                    "event": "clear",
                    "streamSid": self.stream_sid
                }
                await self.twilio_ws.send_text(json.dumps(clear_message))
                logger.info("Cleared Twilio audio buffer (Barge-In).")
            except Exception as e:
                logger.error(f"Failed to clear Twilio: {e}")
                
        # 2. Cancel the background AI task if it is running
        if self.active_ai_task and not self.active_ai_task.done():
            self.active_ai_task.cancel()
            logger.info("Canceled ongoing AI generation task.")
            self.is_processing_ai = False
            
        # 3. Prewarm ElevenLabs for the next response
        if not self.is_processing_ai:
            await self.elevenlabs.prewarm()

    async def trigger_ai_response(self, text: str):
        self.is_processing_ai = True
        
        # Create a queue to allow OpenAI and ElevenLabs to spin up simultaneously
        import asyncio
        token_queue = asyncio.Queue()
        
        # 1. Ask OpenAI what to say next
        ai_reply_stream = OpenAIService.get_response(text, self.state)
        
        async def pump_tokens():
            try:
                async for chunk in ai_reply_stream:
                    await token_queue.put(chunk)
            except Exception as e:
                logger.error(f"Error pumping tokens: {e}")
            finally:
                await token_queue.put(None) # Signal End of Stream
                
        # Launch OpenAI Request in the background immediately
        pump_task = asyncio.create_task(pump_tokens())
        
        async def queue_generator():
            while True:
                chunk = await token_queue.get()
                if chunk is None:
                    break
                yield chunk

        try:
            # 2. Convert to Speech using ElevenLabs
            await self.elevenlabs.generate_audio(queue_generator())
            
            # Ensure pumping completes
            await pump_task
        except asyncio.CancelledError:
            # Clean up if user barges in
            pump_task.cancel()
            raise
        finally:
            # Update order status explicitly if AI marked it confirmed
            if self.state.confirmation_status:
                self.state.stage = "confirmed"
                
            # Save updated memory 
            StateManager.save_session(self.session_id, self.state)
            
            self.is_processing_ai = False

    async def on_audio_received(self, audio_b64: str):
        """ Callback for ElevenLabs sending back audio. Maps back to Twilio. """
        if self.twilio_ws and self.stream_sid:
            media_message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": audio_b64
                }
            }
            try:
                await self.twilio_ws.send_text(json.dumps(media_message))
            except Exception as e:
                logger.error(f"Error sending audio to Twilio: {e}")

    async def stop(self):
        await self.deepgram.close()
        StateManager.delete_session(self.session_id)
        logger.info(f"Orchestrator stopped for session: {self.session_id}")
