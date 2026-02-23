"""
app/services/caldav_sync.py
Synchronisiert lokale Termine mit CalDAV (Nextcloud, Google, etc.).
"""

import caldav
import logging
from typing import List, Optional
from app.models.rule import Base, get_sa_session
from sqlalchemy import Column, Integer, String, Text

logger = logging.getLogger("kukanilea.caldav")

class CalendarConnection(Base):
    __tablename__ = 'calendar_connections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password_encrypted = Column(Text, nullable=False)
    sync_token = Column(String, nullable=True)

class CalDavSync:
    def __init__(self, connection_id: int):
        self.conn_id = connection_id
        self._load_config()

    def _load_config(self):
        session = get_sa_session()
        conn_data = session.query(CalendarConnection).filter_by(id=self.conn_id).first()
        if not conn_data:
            raise ValueError("Kalender-Verbindung nicht gefunden.")
        
        self.url = conn_data.url
        self.username = conn_data.username
        self.password = conn_data.password_encrypted # In Echt entschlüsseln
        session.close()

    def sync_event(self, ical_data: str):
        """Sendet einen Termin an den CalDAV Server."""
        try:
            client = caldav.DAVClient(url=self.url, username=self.username, password=self.password)
            principal = client.principal()
            calendars = principal.calendars()
            if calendars:
                calendar = calendars[0]
                calendar.save_event(ical_data)
                return True
        except Exception as e:
            logger.error(f"CalDAV Sync fehlgeschlagen: {e}")
        return False
