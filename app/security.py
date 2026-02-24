"""
Sicherheits-Layer für KUKANILEA.
Fokus: Prompt-Injection-Prevention und Input-Sanitization.
"""
import bleach
import re
import logging

logger = logging.getLogger("kukanilea.security")

def sanitize_user_input(text: str) -> str:
    """
    Bereinigt User-Input vor der Übergabe an das LLM.
    Entfernt verdächtige Kontrollzeichen und HTML.
    """
    if not text: return ""
    # 1. HTML-Tags entfernen (XSS Schutz)
    text = bleach.clean(text, tags=[], strip=True)
    # 2. Salted Sequence Tag Manipulation verhindern (SST Schutz)
    text = re.sub(r"<salt_.*?>", "[REDACTED_TAG]", text)
    # 3. Mehrfache Newlines normalisieren (Injection-Trick)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def is_malicious_prompt(prompt: str) -> bool:
    """
    Prüft auf bekannte Prompt-Injection Patterns.
    """
    patterns = [
        r"(ignore|forget) (all|previous|prior) (instructions|directions)",
        r"system:.*admin",
        r"you are now.*admin",
        r"output the.*system prompt",
        r"transfer.*data to",
        r"delete all.*"
    ]
    for pattern in patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            logger.warning(f"Verdächtiges Pattern erkannt: {pattern}")
            return True
    return False
