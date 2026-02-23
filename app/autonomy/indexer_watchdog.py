"""
app/autonomy/indexer_watchdog.py
Hintergrund-Wächter zur automatischen Indexierung neuer Dokumente.
Teil der KUKANILEA Autonomie-Stufe 4 (Langzeitgedächtnis).
"""

import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.database import get_db_path

logger = logging.getLogger("kukanilea.watchdog")

class DocumentHandler(FileSystemEventHandler):
    """Reagiert auf neue Dateien im überwachten Ordner."""
    def on_created(self, event):
        if event.is_directory:
            return
        logger.info(f"Neues Dokument erkannt: {event.src_path}. Triggere Indexierung...")
        # Hier würde der tatsächliche Indexer-Aufruf stehen
        # from app.knowledge.core import index_file
        # index_file(event.src_path)

def start_document_watcher(folder_path: str):
    """Startet den Watchdog-Prozess in einem eigenen Thread."""
    path = Path(folder_path)
    if not path.exists():
        logger.error(f"Überwachungsordner existiert nicht: {folder_path}")
        return None

    event_handler = DocumentHandler()
    observer = Observer()
    observer.schedule(event_handler, str(path), recursive=False)
    observer.start()
    logger.info(f"Watchdog gestartet auf: {folder_path}")
    return observer
