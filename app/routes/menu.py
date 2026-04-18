from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.menu_service import MenuService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("/menu/upload")
async def upload_menu(file: UploadFile = File(...)):
    """
    Endpoint to upload a PDF menu. The menu is parsed, structured via AI, and stored in Redis.
    """
    if not file.filename.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF or TXT files are supported.")
        
    try:
        structured_menu = await MenuService.process_menu_file(file)
        return {
            "status": "success", 
            "message": "Menu processed and stored in Redis successfully.",
            "menu_preview": structured_menu
        }
    except Exception as e:
        logger.error(f"Error processing menu upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
