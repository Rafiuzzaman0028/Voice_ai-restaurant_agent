# AI Voice Ordering System MVP

A scalable phone-ordering system integrating Twilio Programmable Voice WebSockets with live deep learning AI providers:
- **Speech-to-Text**: Deepgram (streaming)
- **Conversational Logic**: OpenAI (GPT)
- **Text-to-Speech**: ElevenLabs (streaming)

## Architecture
The application works fully asynchronously through WebSockets. Twilio connects a phone call, our webhook responds with a TwiML to open a `MediaStream` WebSocket to `/ws/media`. 
Audio is continuously routed to Deepgram for low-latency STT. When the caller stops speaking, the transcript traverses out to OpenAI, which determines what missing data is needed to complete the order. Its text output streams directly to ElevenLabs, and the generated TTS is immediately piped back down the same Twilio socket to the caller's phone.

## Documentation
Please reference `docs/setup_guide.md` for information on retrieving correct API keys, configuring your Twilio account, and running via Ngrok.

## Usage
Simply install requirements and run:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
