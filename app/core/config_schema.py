"""
app/core/config_schema.py
Strict configuration validation at boot.
"""
from typing import Dict, Any, List
import logging
from pathlib import Path

logger = logging.getLogger("kukanilea.config_schema")

REQUIRED_KEYS = [
    "USER_DATA_ROOT",
    "CORE_DB",
    "AUTH_DB",
    "SECRET_KEY",
]

def validate_config(config: Dict[str, Any]) -> bool:
    """Validates the application configuration dictionary."""
    is_valid = True
    
    # Check Required Keys
    for key in REQUIRED_KEYS:
        if key not in config or not config[key]:
            logger.critical(f"Config validation failed: Missing required key '{key}'")
            is_valid = False
            
    # Check Path Types and Existence 
    data_root = config.get("USER_DATA_ROOT")
    if data_root:
        path = Path(data_root)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.critical(f"Config validation failed: Cannot create USER_DATA_ROOT at {path}. Error: {e}")
                is_valid = False

    if is_valid:
        logger.info("Config validation passed.")
    return is_valid
