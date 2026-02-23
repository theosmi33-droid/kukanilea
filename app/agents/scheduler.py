"""
app/agents/scheduler.py
Autonome Einsatzplanung und Terminierung für KUKANILEA.
Verwaltet lokale Termine via iCalendar und SQLite.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from icalendar import Calendar, Event
import logging

from app.database import get_db_path, retry_on_lock

logger = logging.getLogger("kukanilea.scheduler")

class Scheduler:
    def __init__(self):
        self.db_path = get_db_path()
        self._ensure_table()

    def _ensure_table(self):
        """Stellt sicher, dass die Termintabelle in SQLite existiert."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    @retry_on_lock()
    def schedule_appointment(self, title: str, description: str, duration_minutes: int, preferred_date: str = None) -> dict:
        """
        Berechnet Startzeit, Endzeit und Fahrpuffer (30 Min) und bucht den Termin.
        preferred_date Format: YYYY-MM-DD
        """
        # Schritt 3: Kalkulation von Start/Ende und Puffer
        travel_buffer = timedelta(minutes=30)
        duration = timedelta(minutes=duration_minutes)
        
        if preferred_date:
            base_time = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=8, minute=0)
        else:
            base_time = datetime.now().replace(hour=8, minute=0) + timedelta(days=1)

        # Suche nach dem nächsten freien Slot (vereinfacht)
        start_time = self._find_free_slot(base_time, duration, travel_buffer)
        end_time = start_time + duration

        # In DB speichern
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO appointments (title, description, start_time, end_time) VALUES (?, ?, ?, ?)",
                (title, description, start_time.isoformat(), end_time.isoformat())
            )
            conn.commit()
        finally:
            conn.close()

        # iCal generieren
        ical_path, ical_data = self._generate_ical(title, description, start_time, end_time)

        # CalDAV Sync (Schritt 3)
        try:
            from app.services.caldav_sync import CalDavSync
            syncer = CalDavSync(connection_id=1)
            syncer.sync_event(ical_data)
        except Exception as e:
            logger.warning(f"CalDAV Sync übersprungen: {e}")

        return {
            "status": "success",
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "ical_path": ical_path
        }

    def _find_free_slot(self, base_time: datetime, duration: timedelta, buffer: timedelta) -> datetime:
        """Findet den nächsten freien Slot unter Berücksichtigung des Puffers."""
        current_attempt = base_time
        
        conn = sqlite3.connect(self.db_path)
        try:
            while True:
                # Prüfe auf Überschneidungen inkl. Puffer
                slot_start = current_attempt - buffer
                slot_end = current_attempt + duration + buffer
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM appointments WHERE NOT (end_time <= ? OR start_time >= ?)",
                    (slot_start.isoformat(), slot_end.isoformat())
                )
                if cursor.fetchone()[0] == 0:
                    return current_attempt
                
                # Nächster Versuch 30 Min später
                current_attempt += timedelta(minutes=30)
                # Feierabend-Check (vereinfacht: nicht nach 18 Uhr starten)
                if current_attempt.hour >= 18:
                    current_attempt = current_attempt.replace(hour=8, minute=0) + timedelta(days=1)
        finally:
            conn.close()

    def _generate_ical(self, title: str, description: str, start: datetime, end: datetime) -> tuple:
        """Erzeugt eine lokale .ics Datei und gibt Daten zurück."""
        cal = Calendar()
        event = Event()
        event.add('summary', title)
        event.add('description', description)
        event.add('dtstart', start)
        event.add('dtend', end)
        cal.add_component(event)

        ical_raw = cal.to_ical()
        output_dir = Path("instance/calendar")
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"Termin_{start.strftime('%Y%m%d_%H%M')}.ics"
        
        with open(filepath, 'wb') as f:
            f.write(ical_raw)
        
        return str(filepath), ical_raw.decode('utf-8')
