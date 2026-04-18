import os
from fastapi import FastAPI
from dotenv import load_dotenv
from app.routes import voice, websocket, menu, chat_test
from app.core.logger import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

app = FastAPI(
    title="AI Voice Ordering MVP",
    description="A Twilio Media Stream powered AI Voice Bot."
)


# Include Routers
app.include_router(voice.router)
app.include_router(websocket.router)
app.include_router(menu.router)
app.include_router(chat_test.router)

@app.get("/")
def health_check():
    return {"status": "running", "service": "voice-ai-mvp"}

@app.on_event("startup")
async def on_startup():
    logger.info("Application starting up... verifying environment variables.")
    # Quick sanity check
    from app.config.settings import settings
    if "?" in settings.TWILIO_ACCOUNT_SID or not settings.OPENAI_API_KEY:
        logger.warning("Missing or unconfigured environment variables. Check .env")