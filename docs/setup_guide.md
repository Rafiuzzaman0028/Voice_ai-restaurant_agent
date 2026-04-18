# Setup Guide: AI Voice Ordering System MVP

This guide will walk you through setting up all the required services and connecting them to your local application.

## 1. Twilio Account & Webhook Setup
### Upgrade Twilio
- First, ensure your Twilio account is upgraded from a trial account, as trial accounts require verifying caller numbers and won't allow random customers to call.
- Once upgraded, log in to the Twilio Console.

### Buy/Connect a Number
- Navigate to **Phone Numbers** > **Manage** > **Active numbers**.
- If you don't have a number, buy one here.
- Click on your phone number to configure it.

### Webhook URL
- Under the **Voice & Fax** section of your number, look for the "A CALL COMES IN" field.
- Set it to **Webhook**, select `HTTP POST`.
- Make sure to add your public URL (e.g. from Ngrok) followed by `/voice`.
  - Example: `https://your-ngrok-url.ngrok.app/voice`
- Click Save.

---

## 2. Deepgram STT (Speech-to-Text)
- Create an account at [Deepgram](https://deepgram.com) and ensure there are available credits.
- Go to the API Keys section in the console.
- Generate a new secret API Key.
- Add this key to your `.env` file under `DEEPGRAM_API_KEY`.

---

## 3. ElevenLabs TTS (Text-to-Speech)
- Create a paid account at [ElevenLabs](https://elevenlabs.io) to ensure optimal streaming latency and API usage.
- Click on your profile picture > **Profile** to find your API key. Add it to `.env` as `ELEVENLABS_API_KEY`.
- You can find the Voice ID of your preferred AI voice by going to the Voices page and copying the Voice ID. Update `ELEVENLABS_VOICE_ID` in `.env`.

---

## 4. OpenAI
- Create an account at [OpenAI](https://platform.openai.com) with billing configured.
- Go to the API keys page and generate a new key.
- Save it in your `.env` under `OPENAI_API_KEY`.

---

## 5. Running Locally with Ngrok
- Install the requirements: `pip install -r requirements.txt`
- Check your `.env` file matches the `.env.example`.
- Start the application:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- Run Ngrok to securely expose your local instance to the web:
  ```bash
  ngrok http 8000
  ```
- Copy the resulting HTTPS forwarding URL and put it in your Twilio settings as described in Step 1.

## 6. Future Deployment
For a production deployment:
- Package this application into a Docker container.
- Deploy the app to a VPS or Cloud service (like AWS EC2, Render, or DigitalOcean App Platform) using HTTPS.
- Use a Redis or database for persistent state-tracking instead of the in-memory `state_manager.py` dictionary.
