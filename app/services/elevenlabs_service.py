import json
import base64
import asyncio
import websockets
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

class ElevenLabsService:
    def __init__(self, audio_callback):
        """
        audio_callback: async function that receives base64 encoded ulaw audio chunks 
        to be sent back to the Twilio WebSocket.
        """
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.ELEVENLABS_VOICE_ID
        self.callback = audio_callback
        self.active_websocket = None

    async def prewarm(self):
        """
        Connects to ElevenLabs in advance so the TLS handshake delay is perfectly
        hidden while the user is still physically speaking.
        """
        if self.active_websocket is not None:
            return # Already prewarmed
            
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id=eleven_turbo_v2_5&output_format=ulaw_8000&optimize_streaming_latency=4"
        try:
            logger.info("ElevenLabs: Pre-warming WebSocket connection...")
            self.active_websocket = await websockets.connect(uri)
            logger.info("ElevenLabs: TLS connection pre-warmed and ready.")
        except Exception as e:
            logger.error(f"ElevenLabs prewarm failed: {e}")
            self.active_websocket = None

    async def generate_audio(self, text_stream):
        """
        Connects to ElevenLabs WebSocket API, streams text tokens, receives audio chunks, 
        and routes them to the callback concurrently.
        """
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream-input?model_id=eleven_turbo_v2_5&output_format=ulaw_8000&optimize_streaming_latency=4"
        
        # Determine whether to use pre-warmed socket or create a new one
        if self.active_websocket is not None:
            websocket = self.active_websocket
            self.active_websocket = None # Consume the socket
            logger.debug("ElevenLabs: Utilizing pre-warmed connection")
            try:
                await self._run_stream(websocket, text_stream, prewarmed=True)
            finally:
                try:
                    await websocket.close()
                except:
                    pass
        else:
            logger.debug("ElevenLabs: Creating fresh connection (Not pre-warmed)")
            try:
                async with websockets.connect(uri) as websocket:
                    await self._run_stream(websocket, text_stream, prewarmed=False)
            except Exception as e:
                logger.error(f"ElevenLabs TTS Error: {e}")

    async def _run_stream(self, websocket, text_stream, prewarmed):
        import time
        start_time = time.time()
        first_chunk_received = False
        
        try:
            # 1. Send the initial configuration message to activate the connected socket
            init_msg = {
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                "xi_api_key": self.api_key,
            }
            await websocket.send(json.dumps(init_msg))

            async def send_text():
                try:
                    async for chunk in text_stream:
                        if chunk:
                            text_msg = {
                                "text": chunk,
                                "try_trigger_generation": True
                            }
                            await websocket.send(json.dumps(text_msg))
                    
                    # Send End of Stream message
                    eos_msg = {"text": ""}
                    await websocket.send(json.dumps(eos_msg))
                except websockets.exceptions.ConnectionClosed:
                    logger.debug("ElevenLabs WS closed before text stream finished")
                    pass

            async def receive_audio():
                nonlocal first_chunk_received
                try:
                    async for message in websocket:
                        response = json.loads(message)
                        if response.get("audio"):
                            if not first_chunk_received:
                                first_chunk_received = True
                                import time
                                logger.info(f"ElevenLabs TTFB: {time.time() - start_time:.3f} seconds")
                            
                            audio_b64 = response["audio"]
                            await self.callback(audio_b64)
                        
                        if response.get("isFinal"):
                            break
                except websockets.exceptions.ConnectionClosed:
                    logger.debug("ElevenLabs WS closed before final audio")
                    pass

            # Run both text sending and audio receiving concurrently
            await asyncio.gather(send_text(), receive_audio())
        except Exception as e:
            logger.error(f"ElevenLabs stream loop error: {e}")
