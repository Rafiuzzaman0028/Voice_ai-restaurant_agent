from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class OrderItem(BaseModel):
    name: str
    size: Optional[str] = None
    toppings: List[str] = Field(default_factory=list)

class OrderDetails(BaseModel):
    items: List[OrderItem] = Field(default_factory=list)
    type: Literal["pickup", "delivery"] = "pickup"
    address: Optional[str] = None

class FinalOrder(BaseModel):
    customer_phone: str
    items: List[OrderItem]
    type: str
    status: Literal["confirmed", "pending", "cancelled"] = "pending"

class SessionState(BaseModel):
    caller_number: str
    call_sid: str
    stage: str = "init"
    transcript_history: List[dict] = Field(default_factory=list)
    order_details: OrderDetails = Field(default_factory=OrderDetails)
    confirmation_status: bool = False
    final_order_json: Optional[dict] = None
    
    def add_transcript(self, role: str, content: str):
        self.transcript_history.append({"role": role, "content": content})
