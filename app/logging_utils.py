import logging
import re

# Simple patterns for PII detection (Email, Phone)
PII_PATTERNS = [
    r'[\w\.-]+@[\w\.-]+\.\w+',  # Email
    r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}' # Generic phone
]

class PIISafeFormatter(logging.Formatter):
    """
    Formatter that redacts PII-like patterns from log messages.
    Compliance: GDPR Art. 25 (Data protection by default).
    """
    def format(self, record: logging.LogRecord) -> str:
        original_msg = super().format(record)
        redacted_msg = original_msg
        for pattern in PII_PATTERNS:
            redacted_msg = re.sub(pattern, "[REDACTED_PII]", redacted_msg)
        return redacted_msg

def setup_secure_logging():
    logger = logging.getLogger("kukanilea")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    formatter = PIISafeFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
    return logger
