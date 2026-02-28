"""
app/agents/input_validator.py
Prompt injection hardening v2.
"""
import re
import logging

logger = logging.getLogger("kukanilea.input_validator")

# Patterns indicating potential override attempts
DANGEROUS_PATTERNS = [
    r"(?i)\bignore\s+all\s+previous\s+instructions\b",
    r"(?i)\bignore\s+system\s+prompt\b",
    r"(?i)\byou\s+are\s+now\b",
    r"(?i)\bfrom\s+now\s+on\b",
    r"(?i)\boverride\b",
    r"(?i)\bforget\s+everything\b",
    r"(?i)\bdisregard\b",
]

def validate_input(user_input: str) -> bool:
    """Returns True if input is safe, False if it contains dangerous patterns."""
    if not user_input:
        return True
        
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, user_input):
            logger.warning(f"Prompt injection attempt detected: '{pattern}' matched in input.")
            return False
            
    return True
