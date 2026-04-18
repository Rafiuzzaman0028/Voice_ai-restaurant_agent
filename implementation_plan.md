# Phase 2: Performance and Interruption Updates

The goal of this phase is to make the Voice AI feel indistinguishable from a human by achieving sub-1-second latency through LLM Token Streaming, gracefully handling user interruptions (Barge-In), and ignoring background noise.

## User Review Required

> [!WARNING]
> These changes represent a major architectural shift from a sequential pipeline (Wait for OpenAI -> Wait for TTS -> Send audio) to a fully concurrent asynchronous streaming pipeline (OpenAI streams to TTS -> TTS streams to Twilio).
> **If you approve this plan, I will heavily refactor `orchestrator.py`, `openai_service.py`, and `elevenlabs_service.py`.**

## Proposed Changes

### 1. Background Noise & VAD Management

#### [MODIFY] [deepgram_service.py](file:///d:/Rafiuzzaman/voice-ai-mvp/app/services/deepgram_service.py)
- **Problem**: 300ms endpointing is too fast, causing background noise to trigger short transcripts. Also, we cannot detect the *exact moment* speech starts for barge-in.
- **Solution**: 
  - Change URL parameters to add `vad_events=true` and increase `endpointing` to `500`.
  - Add a new callback `speech_started_callback` which is fully isolated from the finalized `transcript_callback`.
  - When `data.get("type") == "SpeechStarted"` or an interim transcript arrives with length > 0, trigger the `speech_started_callback` to flag a barge-in.

### 2. LLM Token Streaming to ElevenLabs

#### [MODIFY] [openai_service.py](file:///d:/Rafiuzzaman/voice-ai-mvp/app/services/openai_service.py)
- **Problem**: `get_response` waits for the entire completion before returning.
- **Solution**: 
  - Change `get_response` to be an asynchronous generator (`yield` chunks).
  - Use `client.chat.completions.create(..., stream=True)`.
  - Continuously `yield` text tokens. We also need to build the complete `ai_reply` string locally and append it to the session history *after* the stream completes.
  - Handle tool calls gracefully (if the response is a tool call, we execute the tool and maybe yield the final synthesized text stream).

#### [MODIFY] [elevenlabs_service.py](file:///d:/Rafiuzzaman/voice-ai-mvp/app/services/elevenlabs_service.py)
- **Problem**: `generate_audio` currently accepts a single `str`.
- **Solution**: 
  - Refactor `generate_audio` to accept an `AsyncGenerator[str, None]` (the stream originating from OpenAI).
  - Start an async task to continuously read from the incoming LLM text stream and push chunks to `wss://api.elevenlabs.io`.
  - Listen for the returned audio chunks and run the `audio_callback` to pipe to Twilio.

### 3. Barge-In (Interruption Handling)

#### [MODIFY] [orchestrator.py](file:///d:/Rafiuzzaman/voice-ai-mvp/app/core/orchestrator.py)
- **Problem**: `is_processing_ai` blocks human input and doesn't interrupt the AI.
- **Solution**:
  - Store the AI processing task in an instance variable `self.current_ai_task = asyncio.create_task(...)`.
  - Implement `on_speech_started()`:
    - If `self.current_ai_task` is running, **cancel it** instantly.
    - Send a `"clear"` event to Twilio: `{"event": "clear", "streamSid": self.stream_sid}` to flush Twilio's audio queue instantly.
  - The loop now looks like: Use starts speaking -> Deepgram detects speech -> Cancel AI / clear Twilio -> wait for user to finish -> send final transcript to OpenAI.

## Open Questions
- Streaming tool calls from OpenAI can be slightly tricky. If the AI decides to call the `confirm_and_submit_order` tool, it will stream JSON tokens rather than conversational text. I will implement a buffer to catch tool calls, resolve them, and then seamlessly switch back to a voice text stream. Does this approach work for you?
- Are you comfortable with `orchestrator.py` managing explicit `asyncio.Task` cancellations? It is the most robust way to ensure no "left-over" audio packets are sent to Twilio after a barge-in.
