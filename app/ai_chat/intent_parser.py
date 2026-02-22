import os
import json
import logging
import httpx

logger = logging.getLogger("kukanilea.ai.intent")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = "llama3" # Baseline local model

async def parse_intent(user_input: str) -> dict:
    """
    Parses user input using a local LLM to identify intent and parameters.
    Returns a structured dict with 'action' and 'params'.
    """
    prompt = f"""
    Analyze the user input for a Business OS.
    Available Actions:
    - create_task: title (string)
    - navigate: destination (crm, tasks, knowledge)
    
    User Input: "{user_input}"
    
    Output ONLY valid JSON:
    {{"action": "action_name", "params": {{"key": "value"}}}}
    If no action found, return action "unknown".
    """
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=10.0
            )
            if resp.status_code == 200:
                result = resp.json().get("response", "{}")
                return json.loads(result)
    except Exception as e:
        logger.error(f"Ollama intent parsing failed: {e}")
        
    return {"action": "unknown", "params": {}}
