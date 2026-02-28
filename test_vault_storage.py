import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.core.audit import vault_store_evidence
import hashlib
import json

doc_id = "test-doc-123"
tenant = "KUKANILEA"
payload = {"doc_id": doc_id, "tenant_id": tenant, "data": "test"}
ev_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()

print(f"Storing test evidence: {ev_hash}")
vault_store_evidence(doc_id, tenant, ev_hash, payload)
print("Done.")
