from __future__ import annotations

import json
import logging
from typing import Dict, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError
from app.agents.llm import get_default_provider

logger = logging.getLogger("kukanilea.memory_refiner")

class MemoryImportance(BaseModel):
    score: int = Field(..., ge=1, le=10, description="Wichtigkeit der Information von 1 bis 10.")
    category: str = Field(..., description="Kategorie: FAKT, PRÄFERENZ, SMALLTALK, PROZESS.")
    reason: str = Field(..., description="Kurze Begründung für den Score.")

def calculate_importance(text: str, llm_provider=None) -> Tuple[int, str]:
    """
    Uses the local LLM to evaluate the importance of a piece of information.
    Returns (score, category).
    """
    llm = llm_provider or get_default_provider()
    
    prompt = (
        "Du bist ein Gedächtnis-Analyst für ein Business-OS. Bewerte die folgende Information.\n"
        "Kategorien: FAKT (Termine, Preise, Namen), PRÄFERENZ (Kundenwünsche), SMALLTALK (Belangloses), PROZESS (Bestätigungen).\n"
        "Gib ein JSON zurück: {\"score\": int, \"category\": \"string\", \"reason\": \"string\"}\n\n"
        f"INFORMATION: {text}"
    )
    
    try:
        # Use low temperature for analysis
        response = llm.complete(prompt, temperature=0.0)
        
        # Extract JSON
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(response[start:end+1])
            validated = MemoryImportance.model_validate(data)
            return validated.score, validated.category
            
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        logger.warning(f"Importance scoring failed: {e}")
        
    # Default fallback
    return 5, "FAKT"
