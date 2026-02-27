"""
app/modules/files/logic.py
File management engine for KUKANILEA v2.1 (Nextcloud-style).
Handles Step 86-95 (folders, uploads, versioning, search).
"""

import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

class FileManager:
    def __init__(self, db_ext, user_data_root: Path):
        self.db = db_ext
        self.root = user_data_root / "vault"
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_file(self, tenant_id: str, filename: str, content: bytes) -> str:
        """Step 88: Upload files."""
        f_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        # Physical storage
        tenant_path = self.root / tenant_id
        tenant_path.mkdir(parents=True, exist_ok=True)
        dest = tenant_path / f"{f_id}_{filename}"
        
        with open(dest, "wb") as f:
            f.write(content)
            
        size = len(content)
        
        # DB Record
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO files(id, tenant_id, name, path, size, version, created_at) VALUES (?,?,?,?,?,?,?)",
                (f_id, tenant_id, filename, str(dest), size, 1, now)
            )
            con.commit()
            return f_id
        finally:
            con.close()

    def get_file_path(self, f_id: str) -> Optional[str]:
        """Step 89: Download files (Get path)."""
        con = self.db._db()
        try:
            row = con.execute("SELECT path FROM files WHERE id = ?", (f_id,)).fetchone()
            return row["path"] if row else None
        finally:
            con.close()
            
    def version_file(self, f_id: str, new_content: bytes):
        """Step 90: Version files (Simple increment)."""
        con = self.db._db()
        try:
            row = con.execute("SELECT * FROM files WHERE id = ?", (f_id,)).fetchone()
            if not row: return False
            
            # Save new version (overwrite for now, but in future save separate file)
            with open(row["path"], "wb") as f:
                f.write(new_content)
                
            new_version = row["version"] + 1
            con.execute("UPDATE files SET version = ?, size = ? WHERE id = ?", (new_version, len(new_content), f_id))
            con.commit()
            return True
        finally:
            con.close()

    def search_files(self, tenant_id: str, query: str) -> List[Dict[str, Any]]:
        """Step 93: Search files."""
        con = self.db._db()
        try:
            rows = con.execute(
                "SELECT * FROM files WHERE tenant_id = ? AND name LIKE ?", 
                (tenant_id, f"%{query}%")
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
