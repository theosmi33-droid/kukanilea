"""
app/modules/files/logic.py
File management engine for KUKANILEA v2.1 (Nextcloud-style).
Handles Step 86-95 (folders, uploads, versioning, search).
"""

import os
import uuid
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

class FileManager:
    def __init__(self, db_ext, user_data_root: Path):
        self.db = db_ext
        self.root = user_data_root / "vault"
        self.root.mkdir(parents=True, exist_ok=True)
        self.trash = user_data_root / "trash"
        self.trash.mkdir(parents=True, exist_ok=True)

    def upload_file(self, tenant_id: str, filename: str, content: bytes) -> str:
        """Step 88: Upload files + Step 101: Initial Version."""
        f_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        file_hash = hashlib.sha256(content).hexdigest()
        
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
            # Initial Version
            con.execute(
                "INSERT INTO file_versions(file_id, version, path, size, hash, created_at) VALUES (?,?,?,?,?,?)",
                (f_id, 1, str(dest), size, file_hash, now)
            )
            con.commit()
            return f_id
        finally:
            con.close()

    def version_file(self, f_id: str, new_content: bytes):
        """Step 90/101: Create a new file version."""
        con = self.db._db()
        try:
            row = con.execute("SELECT * FROM files WHERE id = ?", (f_id,)).fetchone()
            if not row: return False
            
            now = datetime.now().isoformat()
            new_version = row["version"] + 1
            file_hash = hashlib.sha256(new_content).hexdigest()
            
            # Save as new physical file for versioning
            ext = Path(row["name"]).suffix
            ver_path = Path(row["path"]).parent / f"{f_id}_v{new_version}{ext}"
            
            with open(ver_path, "wb") as f:
                f.write(new_content)
                
            con.execute("UPDATE files SET version = ?, size = ? WHERE id = ?", (new_version, len(new_content), f_id))
            con.execute(
                "INSERT INTO file_versions(file_id, version, path, size, hash, created_at) VALUES (?,?,?,?,?,?)",
                (f_id, new_version, str(ver_path), len(new_content), file_hash, now)
            )
            con.commit()
            return True
        finally:
            con.close()

    def delete_to_trash(self, f_id: str, tenant_id: str):
        """Step 109: Two-stage deletion (Trash)."""
        con = self.db._db()
        try:
            row = con.execute("SELECT * FROM files WHERE id = ? AND tenant_id = ?", (f_id, tenant_id)).fetchone()
            if not row: return False
            
            now = datetime.now()
            expires = now + timedelta(days=30)
            
            # Move physically
            trash_path = self.trash / tenant_id
            trash_path.mkdir(parents=True, exist_ok=True)
            dest = trash_path / Path(row["path"]).name
            shutil.move(row["path"], dest)
            
            # Update DB
            con.execute(
                "INSERT INTO file_trash(id, tenant_id, original_name, original_path, deleted_at, expires_at) VALUES (?,?,?,?,?,?)",
                (f_id, tenant_id, row["name"], row["path"], now.isoformat(), expires.isoformat())
            )
            con.execute("DELETE FROM files WHERE id = ?", (f_id,))
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
