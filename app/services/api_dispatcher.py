from __future__ import annotations

import json
import logging
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.config import Config
from app.core.lexoffice import LexofficeClient

logger = logging.getLogger("kukanilea.api_dispatcher")

def is_online() -> bool:
    """Checks if the system is online by pinging a reliable target."""
    try:
        # Ping Lexoffice API directly or a stable DNS
        urllib.request.urlopen("https://api.lexoffice.de", timeout=5)
        return True
    except Exception:
        return False

class APIDispatcher:
    """
    Processes the api_outbound_queue in the background.
    Implements retry logic and network awareness.
    """

    def __init__(self, auth_db_path: str):
        self.db_path = auth_db_path

    def process_queue(self):
        if not is_online():
            logger.info("System is OFFLINE. Skipping queue processing.")
            return

        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            # Fetch pending jobs
            jobs = con.execute(
                "SELECT * FROM api_outbound_queue WHERE status = 'pending' AND retry_count < 5"
            ).fetchall()

            if not jobs:
                return

            logger.info(f"Processing {len(jobs)} pending API jobs...")

            for job in jobs:
                self._dispatch_job(con, job)

        except Exception as e:
            logger.error(f"Dispatcher loop failed: {e}")
        finally:
            con.close()

    def _dispatch_job(self, con: sqlite3.Connection, job: sqlite3.Row):
        target = job["target_system"]
        job_id = job["id"]
        
        success = False
        error_msg = ""

        try:
            if target == "lexoffice":
                success, error_msg = self._handle_lexoffice(job)
            else:
                error_msg = f"Unknown target system: {target}"
        except Exception as e:
            error_msg = str(e)

        ts_now = datetime.now(timezone.utc).isoformat() + "Z"
        if success:
            con.execute(
                "UPDATE api_outbound_queue SET status = 'done', last_attempt = ? WHERE id = ?",
                (ts_now, job_id)
            )
        else:
            con.execute(
                "UPDATE api_outbound_queue SET retry_count = retry_count + 1, last_attempt = ?, error_message = ? WHERE id = ?",
                (ts_now, error_msg, job_id)
            )
            # If retry limit reached, mark as failed
            if job["retry_count"] >= 4:
                con.execute(
                    "UPDATE api_outbound_queue SET status = 'failed' WHERE id = ?",
                    (job_id,)
                )
        
        con.commit()

    def _handle_lexoffice(self, job: sqlite3.Row) -> tuple[bool, str]:
        api_key = Config.LEXOFFICE_API_KEY
        if not api_key:
            return False, "API Key missing in config"

        payload = json.loads(job["payload"])
        file_path = Path(job["file_path"])
        
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        client = LexofficeClient(api_key)
        lex_id = client.upload_file(file_path, voucher_type=payload.get("voucher_type", "voucher"))
        
        if lex_id:
            return True, ""
        else:
            return False, "Lexoffice upload failed (see core logs)"

def start_dispatcher_daemon(auth_db_path: str, interval: int = 60):
    """Simple background daemon loop."""
    import threading
    
    dispatcher = APIDispatcher(auth_db_path)
    
    def loop():
        logger.info("API Dispatcher Daemon started.")
        while True:
            dispatcher.process_queue()
            time.sleep(interval)
            
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
