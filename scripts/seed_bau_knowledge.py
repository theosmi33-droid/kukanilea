"""
seed_bau_knowledge.py
Starter-Wissen für das Bauhauptgewerbe (FLISA Edition).
Füttert die lokale KI mit Fachwissen, Normen und Best Practices.
"""
import os
import sys
import json
from pathlib import Path

# Pfade korrigieren
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from app.ai.knowledge import store_entity

BAU_KNOWLEDGE = [
    {
        "type": "norm",
        "id": 1001,
        "text": "VOB/C DIN 18330 - Mauerarbeiten: Regelt die Ausführung von Mauerwerk aus künstlichen Steinen und Platten. Wichtig für Abrechnung: Öffnungen werden bis 2,5m2 übermessen.",
        "meta": {"tags": "VOB, Mauerwerk, DIN18330", "area": "Bauhauptgewerbe"}
    },
    {
        "type": "norm",
        "id": 1002,
        "text": "DIN 1045 - Tragwerke aus Beton, Stahlbeton und Spannbeton: Grundnorm für Betonarbeiten im Hochbau. Definiert Expositionsklassen (z.B. XC1 für trocken) und Festigkeitsklassen.",
        "meta": {"tags": "Beton, Statik, DIN1045", "area": "Hochbau"}
    },
    {
        "type": "best_practice",
        "id": 2001,
        "text": "Bautagebuch-Pflicht: Gemäß HOAI und zur Absicherung gegen Mängelansprüche muss ein tägliches Bautagebuch geführt werden. Wichtig: Witterung, Besondere Vorkommnisse, Personalstärke.",
        "meta": {"tags": "Dokumentation, Recht, Bautagebuch", "area": "Bauleitung"}
    },
    {
        "type": "material",
        "id": 3001,
        "text": "Porenbeton (Gasbeton): Leichtbaustoff mit hoher Wärmedämmung. Verarbeitung erfolgt meist im Dünnbettverfahren. Kritisch: Feuchtigkeitsschutz während der Bauphase.",
        "meta": {"tags": "Baustoffe, Mauerwerk, Dämmung", "area": "Materialkunde"}
    },
    {
        "type": "process",
        "id": 4001,
        "text": "Abnahme nach § 12 VOB/B: Förmliche Abnahme ist der entscheidende Moment für Gefahrenübergang, Beginn der Verjährungsfrist und Fälligkeit der Vergütung.",
        "meta": {"tags": "VOB/B, Recht, Abnahme", "area": "Vertragswesen"}
    }
]

def seed_knowledge():
    print("[START] Fülle AI-Knowledge-Base mit Bauhauptgewerbe-Wissen...")
    count = 0
    for entry in BAU_KNOWLEDGE:
        try:
            store_entity(
                entity_type=entry["type"],
                entity_id=entry["id"],
                text=entry["text"],
                metadata=entry["meta"]
            )
            count += 1
            print(f"[OK] Gespeichert: {entry['type']} #{entry['id']}")
        except Exception as e:
            print(f"[ERR] Fehler bei {entry['id']}: {e}")
    
    print(f"[SUCCESS] {count} Wissens-Chunks erfolgreich in die KI-Datenbank geladen.")

if __name__ == "__main__":
    seed_knowledge()
