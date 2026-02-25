import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import Config
from app.db import AuthDB
from app.auth import hash_password

def seed():
    print(f"Seeding AuthDB at {Config.AUTH_DB}")
    db = AuthDB(Config.AUTH_DB)
    db.init()
    
    now = db._now_iso()
    # Create admin/admin
    db.upsert_user("admin", hash_password("admin"), now)
    db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    
    # Set explicit RBAC roles if possible
    try:
        db.set_user_roles("admin", ["OWNER_ADMIN"], actor_roles=["DEV"])
    except Exception as e:
        print(f"RBAC seeding warning: {e}")
        
    print("[SUCCESS] Seeding abgeschlossen.")

if __name__ == "__main__":
    seed()
