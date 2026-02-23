"""
app/ai/security.py
Implementierung von Salted Sequence Tags zur Abwehr von Prompt-Injection-Angriffen.
Gemäß KUKANILEA Sicherheits-Protokoll 2026.
"""

import re
import secrets


def wrap_with_salt(instruction: str, user_input: str) -> str:
    """
    Umschließt User-Input mit einem kryptografischen Salt.
    Struktur: Instruktion + <salt_hex> + Daten + </salt_hex>
    """
    # Erzeuge einen 16-Byte kryptografischen Salt (32 Zeichen hex)
    salt = secrets.token_hex(16)
    
    # Formatiere den Prompt
    wrapped_prompt = (
        f"{instruction.strip()}\n\n"
        f"<{salt}>\n"
        f"{user_input}\n"
        f"</{salt}>"
    )
    
    return wrapped_prompt

def validate_salted_string(full_string: str) -> bool:
    """
    Validiert, ob ein String korrekt gesalzen ist.
    Nützlich für automatisierte Sicherheitstests.
    """
    # Suche nach dem Muster <hex>...</hex>
    # Note: Using [\s\S]*? to match across newlines robustly.
    match = re.search(r"<([0-9a-f]{32})>[\s\S]*?</\1>", full_string)
    
    if not match:
        return False
        
    return True
