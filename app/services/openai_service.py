import json
import time
import asyncio
from openai import AsyncOpenAI
from app.config.settings import settings
from app.models.order import SessionState, ConversationState
from app.core.logger import get_logger
from app.core.state_manager import global_store

logger = get_logger(__name__)

#client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
client = AsyncOpenAI(api_key=settings.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

class OpenAIService:
    @staticmethod
    def _generate_system_prompt(state: SessionState, menu_json: str) -> str:
        base_prompt = """
        You are a highly realistic, friendly, and efficient front-desk pizza restaurant employee for PizzaBurg.
        
        CRITICAL RULES:
        1. Keep responses completely natural, human-like, and UNDER 12 WORDS when possible.
        2. Use contractions (We'll, That's, You're).
        3. Use occasional filler words like "Sure thing", "Absolutely", "Got it".
        4. NEVER sound robotic. NEVER say "Processing request" or "I understand".
        5. Ask exactly ONE question at a time.
        6. Always reply gracefully to interruptions or corrections (e.g., "Actually make that medium" -> "No problem, changing it to medium").
        7. If uncertain or no input is heard, say "Take your time" or "Are you still there?".
        8. CRITICAL: NEVER write raw JSON, XML, or <function> tags in your conversational output. If you need to update the cart, use the proper function calling API invisibly.
        
        MENU:
        {menu}
        
        Cart Status:
        Order Type: {order_type}
        Items: {items}
        
        You have an 'update_cart_and_state' tool. Use it INSTANTLY when the user provides new valid information, changes items, or if you need to transition to the next state.
        
        CURRENT STATE: {current_state}
        """.format(
            menu=menu_json,
            order_type=state.order_details.type,
            items=state.order_details.model_dump_json(),
            current_state=state.stage.value
        )
        
        state_instructions = ""
        
        if state.stage == ConversationState.GREETING:
            state_instructions = "Objective: Warmly greet the caller and ask if this is for pickup or delivery. (e.g., 'Thanks for calling PizzaBurg, pickup or delivery today?')"
        elif state.stage == ConversationState.ORDER_TYPE:
            state_instructions = "Objective: Identify pickup or delivery. If caller already said it, silently use the tool to advance state to ITEM_COLLECTION."
        elif state.stage == ConversationState.ITEM_COLLECTION:
            state_instructions = "Objective: Ask what they want to order. Extract and save the items using your tool. Only move to ITEM_CUSTOMIZATION if items are collected but missing required details (size, crust)."
        elif state.stage == ConversationState.ITEM_CUSTOMIZATION:
            state_instructions = "Objective: Ask ONLY for required missing modifiers (size, crust) for items in the cart. One question at a time. Do NOT ask flavor if they gave it."
        elif state.stage == ConversationState.UPSELL:
            state_instructions = "Objective: Soft, natural upsell. 'Would you like any drinks or sides with that?' Do not be aggressive. If they say no, move to ADDRESS_COLLECTION or ORDER_REVIEW."
        elif state.stage == ConversationState.ADDRESS_COLLECTION:
            state_instructions = "Objective: Collect the full delivery address. If order type is pickup, silently advance to ORDER_REVIEW."
        elif state.stage == ConversationState.ORDER_REVIEW:
            state_instructions = "Objective: Summarize the complete order clearly. 'Let me confirm: one large pepperoni pizza, regular crust... Is that all correct?' If they confirm, transition to CONFIRMATION."
        elif state.stage == ConversationState.CONFIRMATION:
            state_instructions = "Objective: Confirm the final order. 'Perfect, your order is confirmed. Thanks for calling.' Do not ask more questions."
        elif state.stage == ConversationState.CLOSE:
            state_instructions = "Objective: Warm closing like 'Have a great night.' or 'We'll see you soon.'"
        elif state.stage == ConversationState.HANDOFF_TO_HUMAN:
            state_instructions = "Objective: Say 'One moment, I'll connect you with the store.' Stop taking orders."

        return base_prompt + "\n\nSTATE SPECIFIC INSTRUCTIONS:\n" + state_instructions

    @staticmethod
    async def get_response(transcript: str, state: SessionState):
        """
        Takes the user's latest transcript, updates session state history,
        and generates the AI's next response using GPT model.
        """
        state.add_transcript("user", transcript)
        
        # Fetch dynamic menu from memory
        menu_data = global_store.get("global_restaurant_menu")
        menu_json = menu_data if menu_data else '{"message": "No menu available"}'
        
        system_prompt = OpenAIService._generate_system_prompt(state, menu_json)
        
        # Inject current state context
        system_msg = {
            "role": "system",
            "content": system_prompt
        }
        
        messages = [system_msg] + state.transcript_history
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "update_cart_and_state",
                    "description": "Silent background tool to instantly update cart contents and transition conversational state.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_type": {"type": "string", "enum": ["pickup", "delivery", "dine-in"]},
                            "address": {"type": "string"},
                            "next_state": {"type": "string", "enum": [e.value for e in ConversationState]},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "quantity": {"type": "integer"},
                                        "size": {"type": "string"},
                                        "crust": {"type": "string"},
                                        "half_half": {"type": "string"},
                                        "extra_cheese": {"type": "boolean"},
                                        "toppings_added": {"type": "array", "items": {"type": "string"}},
                                        "toppings_removed": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["name"]
                                }
                            }
                        },
                        "required": ["next_state"]
                    }
                }
            }
        ]
        
        try:
            start_time = time.time()
            logger.info(f"Starting OpenAI request... [State: {state.stage.value}]")
            response_stream = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
#                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=tools,
                temperature=0.3, # keep deterministic state handling
                max_tokens=150,
                stream=True
            )
            
            tool_call_buffer = {"id": None, "name": "", "arguments": ""}
            has_tool_call = False
            full_response_content = ""
            first_token_time = None
            
            try:
                async for chunk in response_stream:
                    if len(chunk.choices) == 0:
                        continue
                    delta = chunk.choices[0].delta
                    
                    if first_token_time is None and (delta.content or delta.tool_calls):
                        first_token_time = time.time()
                        logger.info(f"OpenAI TTFB: {first_token_time - start_time:.3f} seconds")
                        
                    if delta.tool_calls:
                        has_tool_call = True
                        tc = delta.tool_calls[0]
                        if tc.id:
                            tool_call_buffer["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_call_buffer["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_call_buffer["arguments"] += tc.function.arguments
                            
                    elif delta.content:
                        full_response_content += delta.content
                        yield delta.content
            except asyncio.CancelledError:
                if full_response_content:
                    state.add_transcript("assistant", full_response_content)
                raise
            
            if has_tool_call:
                if tool_call_buffer["name"] == "update_cart_and_state":
                    args_str = tool_call_buffer["arguments"]
                    logger.info(f"Tool triggered: update_cart_and_state with {args_str}")
                    
                    try:
                        args = json.loads(args_str)
                        # Process updates
                        if "next_state" in args:
                            try:
                                state.stage = ConversationState(args["next_state"])
                            except Exception as e:
                                logger.error(f"Invalid state transition: {e}")
                                
                        if "order_type" in args:
                            state.order_details.type = args["order_type"]
                        if "address" in args:
                            state.order_details.address = args["address"]
                        if "items" in args:
                            from app.models.order import OrderItem
                            state.order_details.items = [OrderItem(**item) for item in args["items"]]
                            
                        # Complete the final confirmation trigger if we hit CONFIRMATION
                        if state.stage == ConversationState.CONFIRMATION:
                            state.confirmation_status = True
                            state.final_order_json = state.order_details.model_dump()
                            
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool call arguments into JSON.")
                    
                    tool_call_dict = {
                        "id": tool_call_buffer["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call_buffer["name"],
                            "arguments": args_str
                        }
                    }
                    
                    # We inject the tool result and get the AI to actually speak if it didn't already
                    state.transcript_history.append({"role": "assistant", "content": None, "tool_calls": [tool_call_dict]})
                    state.transcript_history.append({"role": "tool", "tool_call_id": tool_call_buffer["id"], "content": f"Cart updated. New state is {state.stage.value}. Please say your short conversational response."})
                    
                    messages = [{"role": "system", "content": OpenAIService._generate_system_prompt(state, menu_json)}] + state.transcript_history
                    
                    second_stream = await client.chat.completions.create(
                        model="llama-3.1-8b-instant",
#                        model="llama-3.3-70b-versatile",

                        messages=messages,
                        temperature=0.4,
                        max_tokens=150,
                        stream=True
                    )
                    
                    second_response_content = ""
                    try:
                        async for chunk in second_stream:
                            if len(chunk.choices) == 0:
                                continue
                            delta = chunk.choices[0].delta
                            if delta.content:
                                second_response_content += delta.content
                                yield delta.content
                    except asyncio.CancelledError:
                        if second_response_content:
                            state.add_transcript("assistant", second_response_content)
                        raise
                            
                    if second_response_content:
                        logger.info(f"AI Said (Post-Tool): {second_response_content.strip()}")
                        state.add_transcript("assistant", second_response_content)
                return
                
            if full_response_content:
                logger.info(f"AI Said: {full_response_content.strip()}")
                state.add_transcript("assistant", full_response_content)
            elif not has_tool_call:
                yield "Got it."
                
        except Exception as e:
            logger.error(f"OpenAI connection error: {e}")
            pass
