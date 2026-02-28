"""
app/core/sync_engine.py
KUKANILEA v2.5 Delta-Sync & Conflict Resolution Engine (Nextcloud-Level).
Handles Task 102 (Delta-Sync) and Task 103 (Conflict Resolution/CRDT).
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("kukanilea.sync")

CHUNK_SIZE = 1024 * 1024 # 1MB Chunks for Task 102

class SyncEngine:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root

    def get_file_chunks(self, file_path: Path) -> List[str]:
        """Task 102: Delta-Sync algorithm part 1 - Chunking."""
        chunks = []
        if not file_path.exists():
            return chunks
            
        with open(file_path, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                # Generate hash for this chunk
                chunk_hash = hashlib.sha256(data).hexdigest()
                chunks.append(chunk_hash)
        return chunks

    def calculate_delta(self, local_path: Path, remote_hashes: List[str]) -> List[int]:
        """Task 102: Identifies which chunk indices have changed."""
        local_hashes = self.get_file_chunks(local_path)
        deltas = []
        
        for i, h in enumerate(local_hashes):
            if i >= len(remote_hashes) or h != remote_hashes[i]:
                deltas.append(i)
                
        return deltas

    def resolve_conflict(self, local_version: int, remote_version: int, content_local: bytes, content_remote: bytes) -> bytes:
        """Task 103: Conflict Resolution (Simple Winning Logic for now)."""
        logger.warning(f"Conflict detected: Local v{local_version} vs Remote v{remote_version}")
        
        # In real CRDT, we would merge operations. 
        # Here we use the higher version number (LWW - Last Write Wins style).
        if local_version >= remote_version:
            return content_local
        return content_remote

    def apply_delta_patch(self, base_file: Path, chunk_index: int, new_data: bytes):
        """Task 102: Patches a specific chunk of a file without rewriting the whole file."""
        # This requires random access file writing (seek/write)
        with open(base_file, "r+b") as f:
            f.seek(chunk_index * CHUNK_SIZE)
            f.write(new_data)
        logger.info(f"Patched chunk {chunk_index} of {base_file.name}")
