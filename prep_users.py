import hashlib
from pathlib import Path
from datetime import datetime
import sys
import os

sys.path.insert(0, str(Path(__file__).parent))
from app.db import AuthDB
import app.config as config

db_path = config.Config.AUTH_DB
db = AuthDB(db_path)
db.init()

pw_hash = hashlib.sha256("password123".encode()).hexdigest()
now = datetime.now().isoformat()

# Insert default tenant
db.upsert_tenant("KUKANILEA", "Kukanilea", now)

for i in range(10):
    username = f"testuser_{i}"
    db.upsert_user(username, pw_hash, now)
    db.upsert_membership(username, "KUKANILEA", "USER", now)

print("Test users created.")
