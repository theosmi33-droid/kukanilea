"""
app/verticals.py
Definition der Branchen-Vorlagen (Vertical Kits) für KUKANILEA.
"""

VERTICAL_KITS = {
    "dach": [
        {"type": "task", "data": {"title": "Gerüst stellen", "status": "todo", "priority": "high"}},
        {"type": "task", "data": {"title": "Aufmaß Dachstuhl", "status": "todo", "priority": "medium"}},
        {"type": "task", "data": {"title": "Ziegel-Lieferung prüfen", "status": "todo", "priority": "medium"}},
        {"type": "tag", "data": {"name": "Aufmaß", "color": "blue"}},
        {"type": "workflow", "data": {"name": "Dachabnahme-Protokoll"}},
    ],
    "shk": [
        {"type": "task", "data": {"title": "Heizungswartung", "status": "todo", "priority": "high"}},
        {"type": "task", "data": {"title": "Rohrverlegung Bad", "status": "todo", "priority": "medium"}},
        {"type": "task", "data": {"title": "Druckprüfung Gasleitung", "status": "todo", "priority": "high"}},
        {"type": "tag", "data": {"name": "Wartung", "color": "green"}},
        {"type": "workflow", "data": {"name": "Dichtheitsprüfung"}},
    ],
    "facility": [
        {"type": "task", "data": {"title": "Objektbegehung", "status": "todo", "priority": "medium"}},
        {"type": "task", "data": {"title": "Zählerstände ablesen", "status": "todo", "priority": "low"}},
        {"type": "task", "data": {"title": "Leuchtmittel-Tausch Tiefgarage", "status": "todo", "priority": "low"}},
        {"type": "tag", "data": {"name": "Checkup", "color": "yellow"}},
        {"type": "workflow", "data": {"name": "Brandschutz-Check"}},
    ],
}
