from app.models.order import SessionState
from typing import Dict

# In-memory dictionary to store session state per twilio stream/call
# session_id -> SessionState
# session_id -> SessionState
active_sessions: Dict[str, SessionState] = {}

# In-memory dictionary to store global settings like the menu
global_store: Dict[str, str] = {}

class StateManager:
    @staticmethod
    def get_or_create_session(session_id: str, caller_number: str, call_sid: str) -> SessionState:
        if session_id not in active_sessions:
            active_sessions[session_id] = SessionState(
                caller_number=caller_number,
                call_sid=call_sid
            )
        return active_sessions[session_id]

    @staticmethod
    def save_session(session_id: str, session: SessionState):
        active_sessions[session_id] = session

    @staticmethod
    def get_session(session_id: str) -> SessionState | None:
        return active_sessions.get(session_id)

    @staticmethod
    def delete_session(session_id: str):
        if session_id in active_sessions:
            session = active_sessions[session_id]
            
            # Save the session to disk before deleting it from memory
            import json
            import os
            from datetime import datetime
            
                
            try:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "session_id": session_id,
                    "caller_number": session.caller_number,
                    "call_sid": session.call_sid,
                    "confirmed": session.confirmation_status,
                    "final_order": session.final_order_json,
                    "transcript": session.transcript_history
                }
                
                file_path = "saved_orders.json"
                saved_data = []
                
                # Load existing array if the file exists
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            saved_data = json.load(f)
                    except json.JSONDecodeError:
                        pass # if it's empty or corrupt, start fresh
                        
                saved_data.append(log_entry)
                
                # Write back pretty-printed structured JSON
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(saved_data, f, indent=4)
                    
            except Exception as e:
                print(f"Error saving session log: {e}")
                
            del active_sessions[session_id]
