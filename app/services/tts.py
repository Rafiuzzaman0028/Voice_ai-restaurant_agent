# from elevenlabs.client import ElevenLabs
# from elevenlabs.play import play
# from app.core.config import ELEVENLABS_API_KEY

# client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# def speak(text):
#     audio = client.text_to_speech.convert(
#         text=text,
#         voice_id="21m00Tcm4TlvDq8ikWAM", # ID for the 'Rachel' voice
#         model_id="eleven_multilingual_v2",
#         output_format="mp3_44100_128"
#     )
#     play(audio)

# import pyttsx3

# engine = pyttsx3.init()

# def speak(text):
#     engine.say(text)
#     engine.runAndWait()

import pyttsx3

def speak(text):
    engine = pyttsx3.init()   # reinitialize every time
    engine.say(text)
    engine.runAndWait()
    engine.stop()