import logging
import json
import os
from datetime import datetime, UTC
from pathlib import Path
from app.logging_utils import PIISafeFormatter

LOG_DIR = Path.home() / ".kukanilea" / "logs"

class JSONFormatter(PIISafeFormatter):
    """
    Structured JSON Formatter for KUKANILEA.
    Ensures machine-readability while maintaining PII-safety.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Redact message using parent logic first
        redacted_msg = super().format(record)
        
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redacted_msg,
            "rid": getattr(record, "rid", "N/A"),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

def setup_observability():
    """Sets up lightweight local observability."""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger("kukanilea")
    logger.setLevel(logging.INFO)
    
    # File Handler for JSON logs
    file_handler = logging.FileHandler(LOG_DIR / "app.log")
    file_handler.setFormatter(JSONFormatter())
    
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)
        
    return logger
