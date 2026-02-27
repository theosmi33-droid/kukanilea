#!/usr/bin/env python3
"""
scripts/ops/verify_vault.py
Verification tool for the KUKANILEA Evidence Vault.
Checks vault entries against current system state to detect manipulations.
"""

import sys
import sqlite3
import hashlib
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import Config
from app.core.audit import vault

def calculate_metadata_hash(payload: dict) -> str:
    """Re-calculates the hash for comparison."""
    # Deterministic JSON string
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def verify_vault():
    print("🔍 KUKANILEA EVIDENCE VAULT INTEGRITY CHECK")
    print("="*60)
    
    entries = vault.verify_integrity()
    total = len(entries)
    valid = 0
    errors = []

    for entry in entries:
        doc_id = entry['doc_id']
        stored_hash = entry['metadata_hash']
        payload = json.loads(entry['payload_json'])
        
        # Recalculate hash from stored payload
        computed_hash = calculate_metadata_hash(payload)
        
        if stored_hash != computed_hash:
            errors.append(f"❌ TAMPERING DETECTED: doc_id {doc_id} (Stored hash mismatch)")
            continue
            
        valid += 1

    print(f"Total Entries: {total}")
    print(f"Verified OK:   {valid}")
    
    if errors:
        print("\n🚨 CRITICAL FAILURES FOUND:")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("\n✅ Vault Integrity: PASS")
        sys.exit(0)

if __name__ == "__main__":
    verify_vault()
