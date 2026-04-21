from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

class ConversationState(str, Enum):
    GREETING = "GREETING"
    ORDER_TYPE = "ORDER_TYPE"
    ITEM_COLLECTION = "ITEM_COLLECTION"
    ITEM_CUSTOMIZATION = "ITEM_CUSTOMIZATION"
    UPSELL = "UPSELL"
    ADDRESS_COLLECTION = "ADDRESS_COLLECTION"
    ORDER_REVIEW = "ORDER_REVIEW"
    CONFIRMATION = "CONFIRMATION"
    CLOSE = "CLOSE"
    HANDOFF_TO_HUMAN = "HANDOFF_TO_HUMAN"

class OrderItem(BaseModel):
    name: str = Field(description="Name of the item (e.g., Margherita Pizza, Garlic Bread)")
    quantity: int = Field(default=1, description="Quantity of this item")
    size: Optional[str] = Field(default=None, description="Size if applicable (e.g., Small, Medium, Large)")
    crust: Optional[str] = Field(default=None, description="Crust type if applicable (e.g., Thin crust, Regular)")
    half_half: Optional[str] = Field(default=None, description="Details if the pizza is half and half")
    extra_cheese: bool = Field(default=False, description="Whether extra cheese was requested")
    toppings_added: List[str] = Field(default_factory=list, description="Extra toppings added")
    toppings_removed: List[str] = Field(default_factory=list, description="Toppings asked to be removed")

class OrderDetails(BaseModel):
    items: List[OrderItem] = Field(default_factory=list)
    type: Optional[Literal["pickup", "delivery", "dine-in"]] = None
    address: Optional[str] = Field(default=None, description="Full delivery address including apartment/unit/landmark if collected")

class FinalOrder(BaseModel):
    customer_phone: str
    items: List[OrderItem]
    type: str
    status: Literal["confirmed", "pending", "cancelled"] = "pending"

class SessionState(BaseModel):
    caller_number: str
    call_sid: str
    stage: ConversationState = Field(default=ConversationState.GREETING)
    transcript_history: List[dict] = Field(default_factory=list)
    order_details: OrderDetails = Field(default_factory=OrderDetails)
    confirmation_status: bool = False
    final_order_json: Optional[dict] = None
    
    def add_transcript(self, role: str, content: str):
        self.transcript_history.append({"role": role, "content": content})
