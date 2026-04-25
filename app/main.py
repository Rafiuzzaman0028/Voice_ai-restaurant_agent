import os
from fastapi import FastAPI
from dotenv import load_dotenv
from app.routes import voice, websocket, menu, chat_test, orders
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
app.include_router(orders.router)

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

    # Load local menu fallback if no upload exists
    try:
        from app.core.state_manager import global_store
        import os
        menu_path = "pizzaburg_menu.txt"
        if os.path.exists(menu_path):
            with open(menu_path, "r", encoding="utf-8") as f:
                global_store["global_restaurant_menu"] = f.read()
                logger.info("Successfully pre-loaded pizzaburg_menu.txt into memory.")
        else:
            logger.warning(f"Could not find {menu_path} on startup.")
    except Exception as e:
        logger.error(f"Error loading menu on startup: {e}")