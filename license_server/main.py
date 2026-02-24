"""
license_server/main.py
Zentraler Lizenz-Server für das ZimaBoard / NAS.
Verwaltet Kunden-Lizenzen und protokolliert Heartbeats.
"""

from fastapi import FastAPI, HTTPException, Query
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

app = FastAPI(title="KUKANILEA License Control")

# Datenbank-Pfad auf der großen HDD
DB_PATH = Path("license_server/data/licenses.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote_licenses (
            license_key TEXT PRIMARY KEY,
            customer_name TEXT,
            status TEXT DEFAULT 'active', -- 'active' or 'blocked'
            last_heartbeat DATETIME,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            timestamp DATETIME,
            ip_address TEXT,
            status_code INTEGER
        )
    """)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/check")
def check_license(key: str = Query(...)):
    """Wird von der Kunden-Software alle 4 Stunden aufgerufen."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.utcnow().isoformat()
    
    try:
        # 1. Lizenz in der Datenbank suchen
        cursor = conn.execute(
            "SELECT customer_name, status FROM remote_licenses WHERE license_key = ?",
            (key,)
        )
        row = cursor.fetchone()
        
        # Logge den Versuch
        status_code = 200
        if not row:
            status_code = 404 # Unbekannt
        elif row['status'] == 'blocked':
            status_code = 403 # Gesperrt
            
        conn.execute(
            "INSERT INTO heartbeat_logs (license_key, timestamp, status_code) VALUES (?, ?, ?)",
            (key, now, status_code)
        )
        
        if row:
            conn.execute(
                "UPDATE remote_licenses SET last_heartbeat = ? WHERE license_key = ?",
                (now, key)
            )
        
        conn.commit()

        if status_code == 404:
            # Wir informieren dich im Log, aber schalten den Kunden NICHT ab
            # (Der Client vertraut seiner lokalen Signatur)
            return {"status": "unknown", "message": "Key not in master database"}
            
        if status_code == 403:
            # Hier lösen wir den verzögerten Kill-Switch beim Kunden aus
            raise HTTPException(status_code=403, detail="License revoked by administrator")

        return {"status": "ok", "customer": row['customer_name']}
        
    finally:
        conn.close()

@app.get("/admin/stats")
def get_stats():
    """Zeigt dir an, welche Kunden online sind."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    licenses = conn.execute("SELECT * FROM remote_licenses").fetchall()
    conn.close()
    return [dict(l) for l in licenses]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
