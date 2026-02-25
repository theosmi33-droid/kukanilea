"""
tests/benchmarks/ocr_accuracy.py
Benchmark-Suite für die OCR-Extraktionsgenauigkeit von KUKANILEA.
Prüft Heuristik vs. LLM-Refinement.
"""

import time
import json
import os
import sys

# Pfad-Setup für lokale Imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.ai.extraction_agent import extraction_agent

def run_benchmark():
    test_cases = [
        {
            "id": "rechnung_wuerth_01",
            "ocr_text": "ADOLF WUERTH GmbH & Co. KG... Rechnungsnummer: RE-12345... Datum: 12.02.2026... Gesamt netto: 100,00... MwSt 19%: 19,00... Gesamtbetrag: 119,00 EUR",
            "expected": {
                "vendor_name": "Würth",
                "total_amount": 119.0,
                "vat_valid": True
            }
        },
        {
            "id": "rechnung_invalid_vat",
            "ocr_text": "Eisen-Karl... Summe: 200,00... Netto: 100,00... MwSt: 19,00",
            "expected": {
                "vendor_name": "Eisen-Karl",
                "vat_valid": False
            }
        },
        {
            "id": "auto_learning_test",
            "ocr_text": "Spezial-Bau GmbH... Projekt: 999... Betrag: 500,00",
            "learning_step": {
                "vendor_name": "Spezial-Bau (Gelernt)",
                "kdnr": "999"
            },
            "expected": {
                "vendor_name": "Spezial-Bau (Gelernt)"
            }
        }
    ]

    print(f"--- KUKANILEA OCR BENCHMARK START ---")
    results = []
    
    for case in test_cases:
        if "learning_step" in case:
            print(f"SImuliere Lern-Schritt für {case['id']}...")
            from app.core.ocr_learning import record_correction
            # Wir simulieren eine Korrektur durch den Nutzer
            record_correction({}, case["learning_step"], case["ocr_text"])

        start_time = time.time()
        extracted = extraction_agent.refine_extraction(case["ocr_text"])
        duration = time.time() - start_time
        
        # Scoring
        correct = True
        for key, val in case["expected"].items():
            if extracted.get(key) != val:
                correct = False
        
        results.append({
            "id": case["id"],
            "success": correct,
            "duration": duration,
            "data": extracted
        })
        
        status = "PASS" if correct else "FAIL"
        print(f"[{status}] {case['id']} - {duration:.2f}s")

    # Summary
    success_rate = (sum(1 for r in results if r["success"]) / len(results)) * 100
    avg_duration = sum(r["duration"] for r in results) / len(results)
    
    print(f"--- SUMMARY ---")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Avg Duration: {avg_duration:.2f}s")
    
    if success_rate < 80:
        print("WARN: Accuracy below threshold!")

if __name__ == "__main__":
    run_benchmark()
