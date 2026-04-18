import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we're running with the right python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.services.openai_service import OpenAIService
from app.services.elevenlabs_service import ElevenLabsService
from app.models.order import SessionState

async def test_openai():
    print("--- Testing OpenAI Service ---")
    state = SessionState(call_sid="TEST1234", caller_number="+1234567890")
    
    # Simulate a user saying they want a pizza
    user_input = "Hi, I would like to order a large pizza."
    print(f"User: {user_input}")
    
    ai_response_stream = OpenAIService.get_response(user_input, state)
    
    print("AI: ", end="", flush=True)
    full_text = ""
    async for chunk in ai_response_stream:
        print(chunk, end="", flush=True)
        full_text += chunk
    print("\n")
    return full_text

async def string_to_stream(text: str):
    yield text

async def test_elevenlabs(text: str):
    print("--- Testing ElevenLabs Service ---")
    
    audio_chunks = []
    
    async def mock_audio_callback(audio_b64: str):
        audio_chunks.append(audio_b64)
        print(f"Received audio chunk of length: {len(audio_b64)}")

    tts_service = ElevenLabsService(mock_audio_callback)
    
    print(f"Sending text to ElevenLabs stream generator: '{text}'")
    await tts_service.generate_audio(string_to_stream(text))
    
    if len(audio_chunks) > 0:
        print("\n[SUCCESS] ElevenLabs connected and successfully generated audio stream!")
    else:
        print("\n[FAILED] ElevenLabs failed to generate audio.")

async def main():
    print("Starting Local Integration Tests...")
    
    # Test 1: OpenAI
    ai_reply = await test_openai()
    
    # Test 2: ElevenLabs
    if ai_reply:
        await test_elevenlabs(ai_reply)

if __name__ == "__main__":
    asyncio.run(main())
