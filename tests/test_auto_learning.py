from __future__ import annotations

import os
import sys
from unittest.mock import patch

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.rag_sync import learn_from_correction

def test_auto_learning():
    print("Testing KUKANILEA Auto-Learning OCR...")
    
    tenant_id = "test_tenant"
    file_name = "rechnung_schmidt.pdf"
    ocr_text = "Rechnung Nr 12345, Betrag 500 EUR..."
    
    # AI suggested SONSTIGES, but it's actually RECHNUNG
    suggestions = {
        "doctype_suggested": "SONSTIGES",
        "kdnr_suggested": "000"
    }
    
    answers = {
        "doctype": "RECHNUNG",
        "kdnr": "10005"
    }
    
    # Mock memory manager
    with patch("app.agents.memory_store.MemoryManager.store_memory", return_value=True) as mock_store:
        success = learn_from_correction(
            tenant_id=tenant_id,
            file_name=file_name,
            text=ocr_text,
            original_suggestions=suggestions,
            final_answers=answers
        )
        
        assert success is True
        assert mock_store.called
        
        # Check if correct arguments were passed
        args, kwargs = mock_store.call_args
        stored_content = kwargs["content"]
        print(f"Learned content:\n{stored_content}")
        
        assert "RECHNUNG" in stored_content
        assert "10005" in stored_content
        assert kwargs["metadata"]["type"] == "ocr_correction"

    print("Auto-Learning Test: PASS")

if __name__ == "__main__":
    test_auto_learning()
