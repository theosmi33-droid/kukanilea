"""
app/verticals.py
Definition der Branchen-Vorlagen (Vertical Kits) für KUKANILEA.
"""

VERTICAL_KITS = {
    "dach": [
        {"type": "task", "data": {"title": "Gerüst stellen", "priority": "high"}},
        {"type": "task", "data": {"title": "Aufmaß Dachstuhl", "priority": "medium"}},
        {"type": "workflow", "data": {"name": "Dachabnahme-Protokoll"}}
    ],
    "shk": [
        {"type": "task", "data": {"title": "Heizungswartung", "priority": "high"}},
        {"type": "task", "data": {"title": "Rohrverlegung Bad", "priority": "medium"}},
        {"type": "workflow", "data": {"name": "Dichtheitsprüfung"}}
    ],
    "facility": [
        {"type": "task", "data": {"title": "Objektbegehung", "priority": "medium"}},
        {"type": "task", "data": {"title": "Zählerstände ablesen", "priority": "low"}},
        {"type": "workflow", "data": {"name": "Brandschutz-Check"}}
    ]
}
