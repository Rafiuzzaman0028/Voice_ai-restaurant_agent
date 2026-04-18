import pymupdf
import json
from fastapi import UploadFile
from app.config.settings import settings
from openai import AsyncOpenAI
from app.core.logger import get_logger
from app.core.state_manager import global_store

logger = get_logger(__name__)

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class MenuService:
    @staticmethod
    async def process_menu_file(file: UploadFile) -> dict:
        """
        Extracts text from PDF, runs through an OpenAI structured cleaner,
        and saves it in Redis.
        """
        logger.info(f"Processing uploaded menu file: {file.filename}")
        
        # Read the file contents
        content = await file.read()
        
        # Extract text based on file format
        raw_text = ""
        if file.filename.endswith(".pdf"):
            doc = pymupdf.open(stream=content, filetype="pdf")
            for page in doc:
                raw_text += page.get_text()
            doc.close()
        else:
            # Basic fallback for txt files
            logger.warning("Unsupported file type or extension, treating as raw text.")
            raw_text = content.decode("utf-8")

        if not raw_text.strip():
            raise ValueError("Could not extract any text from the provided document.")

        structured_menu = await MenuService._clean_menu_with_openai(raw_text)
        
        # Save to memory
        logger.info("Saving structured menu to memory.")
        global_store["global_restaurant_menu"] = json.dumps(structured_menu)
        
        return structured_menu

    @staticmethod
    async def _clean_menu_with_openai(raw_text: str) -> dict:
        """
        Uses OpenAI to convert raw scraped text into a clean JSON structure.
        """
        logger.info("Sending raw text to OpenAI for structuring.")
        
        prompt = """
        You are a menu structuring assistant. 
        Extract the following raw restaurant menu text into a clean JSON format.
        The JSON should have a key "categories" which is a list of categories (e.g., Starters, Pizzas, Drinks).
        Each category should contain a "name" and a list of "items".
        Each item must have a "name", "description", and a "price" (if found, otherwise null). 
        Make sure the output is pure valid JSON without markdown wrapping.
        """
        
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": raw_text}
                ],
                response_format={ "type": "json_object" }
            )
            
            clean_json = response.choices[0].message.content
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"Failed to cleanly parse menu via OpenAI: {e}")
            raise ValueError("Failed to cleanly parse menu.")
