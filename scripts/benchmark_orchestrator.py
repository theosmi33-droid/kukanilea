#!/usr/bin/env python3
"""
scripts/benchmark_orchestrator.py
Benchmark, Latenz-Messung und Halluzinations-Prüfung für Orchestrator V2.
"""

import asyncio
import time
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.orchestrator_v2 import delegate_task
from app.services.price_service import PriceService

logging.basicConfig(level=logging.WARNING)

async def run_benchmark():
    print("🚀 Starte Orchestrator V2 Benchmark...")
    
    # 1. Latenz-Messung
    test_inputs = [
        "Bitte Angebot #100 für Material vorbereiten.",
        "Rechnung abgleich durchführen",
        "Neuen Termin mit Kunde planen"
    ]
    
    total_time = 0
    print("\\n⏳ Latenz-Messung:")
    for task in test_inputs:
        start_t = time.perf_counter()
        try:
            res = await delegate_task(task)
        except Exception as e:
            res = str(e)
        end_t = time.perf_counter()
        latency = (end_t - start_t) * 1000
        total_time += latency
        print(f"Task: '{task[:20]}...' | Latenz: {latency:.2f} ms")
    
    avg_latency = total_time / len(test_inputs)
    print(f"➡️ Durchschnittliche Latenz: {avg_latency:.2f} ms")

    # 2. Halluzinations-Rate berechnen (PriceService)
    print("\\n🕵️ Halluzinations-Prüfung (PriceService):")
    price_service = PriceService()
    
    test_articles = [
        "Waschbecken Keramik Standard",  # Existiert (Seeded)
        "Einhandmischer Chrom",          # Existiert
        "Rohrbogen Kupfer 15mm",         # Existiert
        "Zement CEM II 25kg",            # Existiert
        "Hyperraum-Schlüssel",           # Fake
        "Fluxkompensator",               # Fake
        "Giga-Watte",                    # Fake
    ]
    
    fails = 0
    success = 0
    
    for article in test_articles:
        price_info = price_service.get_price(article)
        if price_info is None:
            # System erkennt korrekterweise, dass es das nicht gibt -> Schätzung -> Flag
            # In der echten Kette würde das als 'estimated' markiert und vom Observer geblockt.
            success += 1
        elif price_info.get("estimated", False):
            success += 1
        else:
            # Wir haben einen Preis gefunden
            if article in ["Hyperraum-Schlüssel", "Fluxkompensator", "Giga-Watte"]:
                # Halluzination! Es hat einen Fake-Artikel in der DB gefunden oder generiert
                fails += 1
                print(f"❌ FAIL: Halluzinierter Preis für '{article}' gefunden!")
            else:
                success += 1
    
    hallucination_rate = (fails / len(test_articles)) * 100
    print(f"➡️ Halluzinations-Rate: {hallucination_rate:.1f}% (Erwartet: 0.0%)")

    print("\\n✅ Benchmark abgeschlossen.")
    print("="*40)
    print(f"Performance Score : {1000/avg_latency if avg_latency > 0 else 0:.2f} (höher ist besser)")
    print(f"Precision Score   : {100 - hallucination_rate:.1f}%")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
