import time
import uuid
from fastapi import HTTPException, Request, Response
from typing import Dict

# Server-side session store (Local-first, in-memory for now)
# In high-availability scenarios, this would use SQLite/Redis
sessions: Dict[str, dict] = {}

SESSION_IDLE_TIMEOUT = 1800  # 30 minutes in seconds

def create_session(user_id: str, tenant_id: str, role: str) -> str:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "last_activity": time.time()
    }
    return session_id

def validate_session(session_id: str) -> dict:
    if session_id not in sessions:
        raise HTTPException(status_code=401, detail="Session invalid or expired")
    
    session = sessions[session_id]
    if time.time() - session["last_activity"] > SESSION_IDLE_TIMEOUT:
        del sessions[session_id]
        raise HTTPException(status_code=401, detail="Session timed out due to inactivity")
    
    # Update activity for idle timeout
    session["last_activity"] = time.time()
    return session

def invalidate_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
