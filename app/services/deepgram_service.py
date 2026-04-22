import asyncio
import json
from websockets import connect
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

class DeepgramService:
    def __init__(self, transcript_callback, interim_callback=None):
        """
        transcript_callback: async function that receives the finalized text string.
        interim_callback: async function that fires on the very first detection of speech.
        """
        self.api_key = settings.DEEPGRAM_API_KEY
        self.websocket = None
        self.callback = transcript_callback
        self.interim_callback = interim_callback
        self.is_speaking = False

#         self.url = "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1&model=nova-2&interim_results=true&endpointing=250&utterance_end_ms=1000&vad_events=true"
        # Moderated endpointing (600ms) to prevent cutting off callers, using phonecall model for 8000hz Twilio audio
        self.url = "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1&model=nova-2-phonecall&interim_results=true&endpointing=350&utterance_end_ms=1000&vad_events=true"
#        self.url = "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=mulaw&sample_rate=8000&channels=1&interim_results=true&endpointing=250"
    async def connect(self):
        try:
            self.websocket = await connect(
                self.url,
                
                additional_headers={"Authorization": f"Token {self.api_key}"}
            )
            logger.info("Deepgram STT Connected")
            asyncio.create_task(self._receive_messages())
        except Exception as e:
            logger.error(f"Deepgram STT Connection failed: {e}")

    async def _receive_messages(self):
        if not self.websocket:
            return
            
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                # Check for transcript
                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")
                        is_final = data.get("is_final", False)
                        speech_final = data.get("speech_final", False)
                        
                        if transcript:
                            # Trigger prewarming on the VERY FIRST word detected
                            if not is_final and not speech_final and not self.is_speaking:
                                self.is_speaking = True
                                if self.interim_callback:
                                    logger.debug(f"Deepgram Interim Triggered: {transcript}")
                                    asyncio.create_task(self.interim_callback(transcript))

                            # If someone finishes speaking a sentence
                            if is_final or speech_final:
                                self.is_speaking = False
                                logger.debug(f"Deepgram STT Final: {transcript}")
                                await self.callback(transcript)
                                
                elif data.get("type") == "UtteranceEnd":
                    # Deepgram forcefully ends a noisy utterance
                    self.is_speaking = False
                                
        except Exception as e:
            logger.error(f"Deepgram STT Error receiving message: {e}")

    async def send_audio(self, audio_data: bytes):
        if self.websocket:
            try:
                await self.websocket.send(audio_data)
            except Exception as e:
                logger.debug(f"Deepgram WebSocket sending failed: {e}")
                self.websocket = None

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("Deepgram STT Disconnected")
