from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def log_event(event_type: str, data: Any):
    """
    Logs a structured event to instance/agent_events.jsonl.
    Uses UTC ISO-8601 timestamps for GoBD compliance.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "type": event_type,
        "data": data
    }

    log_dir = "instance"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_path = os.path.join(log_dir, "agent_events.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "
")
