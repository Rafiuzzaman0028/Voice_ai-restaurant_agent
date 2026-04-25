# Voice AI MVP: Project Analysis & Upgrade Progress

## 1. Current Upgrade Progress

The Voice AI MVP has seen significant architectural improvements to prepare for production deployment on AWS:
- **Single-LLM Flow Transition:** We successfully transitioned from a multi-stage LLM pipeline to a streamlined, single-LLM architecture. This eliminates mid-conversation delays and improves the conversational coherence of the AI, allowing it to handle complex interactions (like address collection and menu queries) in fewer hops.
- **Persistent Local State & Menu Verification:** We implemented persistent menu loading using a local `pizzaburg_menu.txt` file as a fallback, ensuring that the AI can instantly retrieve accurate product options upon server start/restart without relying heavily on external storage dependencies.
- **Improved Connection Stability:** Fixed "phantom calls" by enforcing explicit Twilio REST API termination in the orchestrator, preventing hanging sockets and saving API costs.
- **State Management Refactor:** Completed the refactoring of how completed orders are saved.

### The New Saved Orders Architecture
Instead of appending all call data into a single `saved_orders.json` file—which becomes inefficient and difficult to parse over time—the system now saves every call's output as an individual JSON file inside a newly created `saved_orders/` folder. 
- **Format:** `order_<timestamp>_<session_id>.json`
- **Benefit:** Easily accessible by endpoints without locking issues or parsing giant JSON arrays.

**New API Endpoints Added for Backend Integration:**
- `GET /orders` -> Returns an array of available order filenames.
- `GET /orders/{filename}` -> Returns the precise, structured JSON containing that call's transcript, caller ID, and the finalized order details.

---

## 2. Expected Latency Performance on AWS (Live Calls)

Once this code is pulled to your AWS Server, you can expect the following latency profile for live interactions. 

### Latency Breakdown for a Single Interaction Turn
1. **Speech-To-Text (Deepgram):** `~200ms - 300ms` (AWS us-east/us-west proximity to Deepgram will dictate the lower bound here).
2. **LLM Processing (Llama 3.1 8b Instant via Groq/TogetherAI):** `~300ms - 500ms` (TTFT - Time To First Token). This is exceptionally fast because we removed intermediate routing LLMs.
3. **Text-To-Speech Generation:** `~200ms - 400ms` (Streaming first-byte to Twilio Media Streams).
4. **Network / WebSocket Roundtrip (AWS <-> Twilio):** `~50ms - 150ms`.

**Total Expected End-to-End Latency:** **~750ms to 1.3 seconds** per turn. 
*(Anything under 1.5 seconds feels like a natural human conversation pause).*

### Latency by Scenario

- **Initial Greeting / Connection:** 
  - *Scenario:* User connects via Twilio. 
  - *Performance:* We implemented a slight delay specifically for the initial connection to prevent the STT/TTS engine from cutting off network initialization. Once connected, the first response should hit the user's ear within `~1.5s` of the phone picking up.
  
- **Mid-Conversation Ordering (e.g., "I want a large pepperoni pizza"):** 
  - *Scenario:* Standard item addition. 
  - *Performance:* Fastest turn-around (`~800ms - 1.0s`). Deepgram rapidly identifies the endpoint, and the LLM instantly recognizes the entity.
  
- **Barge-in / Interruptions:** 
  - *Scenario:* The AI is speaking, and the customer interrupts ("Wait, actually make it a medium").
  - *Performance:* Highly responsive. As soon as Deepgram detects audio input matching speech, the system halts the current TTS playback via the WebSocket and begins processing the new STT stream. Expected interruption-to-new-response time is `~1.2s`.

- **Call Wrap-up & Order Finalization:**
  - *Scenario:* Customer says "That's all." AI validates the address and finalizes.
  - *Performance:* May take slightly longer (`~1.2s - 1.5s`) as the LLM formats the final JSON payload confirming the full order, which the backend then saves to disk instantly after the socket closes.

---

## 3. Deployment Recommendations for AWS

To ensure the latency numbers above are met in your AWS environment:
1. **Region Selection:** Ensure your AWS instance is deployed in a region physically closest to your Twilio Edge location and your STT/LLM provider's primary data centers (e.g., `us-east-1` or `us-west-2`).
2. **Concurrency:** FastAPI and Uvicorn should be run with multiple workers (e.g., `uvicorn app.main:app --workers 4`) to handle simultaneous incoming WebSockets without blocking the event loop.
3. **Directory Permissions:** Ensure the process running the application on AWS has write permissions to create and populate the `saved_orders/` directory.
