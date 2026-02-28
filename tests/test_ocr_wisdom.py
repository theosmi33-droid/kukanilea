from __future__ import annotations

import os
import sys
from unittest.mock import patch

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.ocr_corrector import OCRCorrector

def test_ocr_wisdom_injection():
    print("Testing KUKANILEA OCR Wisdom Injection...")
    
    tenant_id = "T1"
    corrector = OCRCorrector(tenant_id)
    
    # Mock corrections in memory
    mock_corrections = [
        {
            "content": "KORREKTUR-WISSEN:\nDokument 'rechnung.pdf' war als SONSTIGES erkannt, ist aber RECHNUNG.\n\nKontext-Auszug:\n...",
            "metadata": {"type": "ocr_correction"}
        }
    ]
    
    with patch("app.agents.memory_store.MemoryManager.retrieve_context", return_value=mock_corrections):
        base_prompt = "Bitte analysiere das Dokument."
        final_prompt = corrector.apply_corrections_to_prompt(base_prompt, "Rechnungstext")
        
        print(f"Final prompt extract:\n{final_prompt[:200]}...")
        assert "frühere Korrekturen" in final_prompt
        assert "RECHNUNG" in final_prompt
        assert base_prompt in final_prompt

    print("OCR Wisdom Injection Test: PASS")

if __name__ == "__main__":
    test_ocr_wisdom_injection()
