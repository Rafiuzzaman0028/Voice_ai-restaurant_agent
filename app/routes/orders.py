import os
import json
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

router = APIRouter(
    prefix="/orders",
    tags=["orders"]
)

ORDERS_DIR = "saved_orders"

@router.get("", response_model=List[str])
async def list_orders():
    """
    Returns a list of all saved order filenames.
    """
    if not os.path.exists(ORDERS_DIR):
        return []
        
    try:
        # List all json files in the directory
        files = [f for f in os.listdir(ORDERS_DIR) if f.endswith('.json')]
        # Sort them by name (which includes timestamp, so chronological)
        files.sort(reverse=True)
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading orders directory: {str(e)}")

@router.get("/{filename}", response_model=Dict[str, Any])
async def get_order(filename: str):
    """
    Returns the complete JSON payload of a specific order by filename.
    """
    if not filename.endswith('.json'):
        filename = f"{filename}.json"
        
    file_path = os.path.join(ORDERS_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Order not found")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading order file: {str(e)}")
