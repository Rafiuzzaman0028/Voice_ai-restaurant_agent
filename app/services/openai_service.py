import json
import time
from openai import AsyncOpenAI
from app.config.settings import settings
from app.models.order import SessionState
from app.core.logger import get_logger
from app.core.state_manager import global_store

logger = get_logger(__name__)

#client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
client = AsyncOpenAI(api_key=settings.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

class OpenAIService:
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
        
        system_prompt = """
        You are an AI restaurant order-taking assistant.
        
        RULES:
        - Be EXTREMELY concise. Never use more than 1 or 2 short sentences.
        - NEVER say "I think there may be a misunderstanding" or over-apologize. Just smoothly guide the user forward.
        - If a user says something that sounds similar to a menu item (e.g., "extra keys" instead of "extra cheese", or "margarita" instead of "Margherita"), ALWAYS use phonetic context to map it to the correct menu item. You are dealing with imperfect speech-to-text.
        - Ask exactly ONE question at a time.
        - Only offer items from the provided JSON menu below.
        - Confirm the complete order before finalizing.
        - Trigger the 'confirm_and_submit_order' tool ONLY when the user explicitly confirms the final order.
        
        Menu:
        {menu}
        
        Current Order State:
        - Items: {items}
        - Stage: {stage}
        """
        
        # Inject current state context roughly into the prompt
        system_msg = {
            "role": "system",
            "content": system_prompt.format(
                menu=menu_json,
                items=state.order_details.model_dump_json(),
                stage=state.stage
            )
        }
        
        messages = [system_msg] + state.transcript_history
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "confirm_and_submit_order",
                    "description": "Submit a final confirmed order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "quantity": {"type": "integer"}
                                    }
                                }
                            },
                            "order_type": {"type": "string", "enum": ["pickup", "delivery"]}
                        },
                        "required": ["items", "order_type"]
                    }
                }
            }
        ]
        
        try:
            start_time = time.time()
            logger.info("Starting OpenAI request...")
            response_stream = await client.chat.completions.create(
#                model="gpt-4o-mini",
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=tools,
                temperature=0.3,
                max_tokens=150,
                stream=True
            )
            
            tool_call_buffer = {"id": None, "name": "", "arguments": ""}
            has_tool_call = False
            full_response_content = ""
            first_token_time = None
            
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
            
            if has_tool_call:
                if tool_call_buffer["name"] == "confirm_and_submit_order":
                    args = tool_call_buffer["arguments"]
                    logger.info(f"Tool triggered: confirm_and_submit_order with {args}")
                    
                    state.confirmation_status = True
                    try:
                        state.final_order_json = json.loads(args)
                    except json.JSONDecodeError:
                        logger.error("Failed to parse tool call arguments into JSON.")
                    
                    tool_call_dict = {
                        "id": tool_call_buffer["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call_buffer["name"],
                            "arguments": tool_call_buffer["arguments"]
                        }
                    }
                    
                    state.transcript_history.append({"role": "assistant", "content": None, "tool_calls": [tool_call_dict]})
                    state.transcript_history.append({"role": "tool", "tool_call_id": tool_call_buffer["id"], "content": "Order confirmed and submitted successfully to backend."})
                    
                    messages = [system_msg] + state.transcript_history
                    
                    second_stream = await client.chat.completions.create(
#                        model="gpt-4o-mini",
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=150,
                        stream=True
                    )
                    
                    second_response_content = ""
                    async for chunk in second_stream:
                        if len(chunk.choices) == 0:
                            continue
                        delta = chunk.choices[0].delta
                        if delta.content:
                            second_response_content += delta.content
                            yield delta.content
                            
                    state.add_transcript("assistant", second_response_content)
                return
                
            if full_response_content:
                state.add_transcript("assistant", full_response_content)
            elif not has_tool_call:
                yield "Got it."
                
        except Exception as e:
            logger.error(f"OpenAI connection error: {e}")
            yield "I'm sorry, I encountered an issue. Can you please repeat that?"
