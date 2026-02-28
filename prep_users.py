import hashlib
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import app.config as config
from app.db import AuthDB

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
