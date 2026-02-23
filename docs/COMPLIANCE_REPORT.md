# KUKANILEA Compliance & Certification Report
**Version:** 1.5.0
**Datum:** 23. Februar 2026
**Status:** Audit-Ready (Autonomie-Stufe 5)

## 1. Übersicht
Dieser Bericht dokumentiert die technischen und organisatorischen Maßnahmen (TOMs) des KUKANILEA Systems zur Sicherstellung der Datenintegrität, Revisionssicherheit und des Datenschutzes in einer autonomen Agenten-Umgebung.

---

## 2. GoBD-Konformität (Ordnungsmäßigkeit & Unveränderbarkeit)
KUKANILEA erfüllt die Anforderungen der GoBD für digitale Belege und Prozesse durch folgende Mechanismen:

### 2.1. Beleg-Immutabilität (Unveränderbarkeit)
Jeder durch den `MasterAgent` oder den `QuoteGenerator` erstellte Beleg (Angebot/Rechnung) wird im Moment der Generierung kryptographisch gesichert.
- **Technik:** SHA-256 Hashing.
- **Speicherung:** Der Hash wird zusammen mit dem Dateipfad und einem Zeitstempel in der Tabelle `document_hashes` (SQLAlchemy Model: `DocumentHash`) revisionssicher geloggt.
- **Audit-Pfad:** Nachträgliche Manipulationen am Dateisystem werden durch einen Abgleich gegen die Hash-Datenbank sofort erkannt und im Audit-Log als Sicherheitsereignis markiert.

### 2.2. Preis-Integrität
Die Angebotskalkulation erfolgt nicht rein generativ, sondern über den `PriceService`.
- **Validierung:** Preise werden gegen eine lokale SQLite FTS5 Datenbank (`article_search`) geprüft.
- **Veto-Recht:** Der `ObserverAgent` blockiert den Versand von Angeboten, wenn Preise geschätzt werden mussten oder unplausibel hohe Abweichungen (> 3%) vorliegen.

---

## 3. DSGVO-Konformität (Datenschutz & Transparenz)
KUKANILEA folgt dem Prinzip "Privacy by Design" (Art. 25 DSGVO).

### 3.1. Datenminimierung & Löschroutinen
Der `PrivacyManager` automatisiert die Einhaltung des Rechts auf Vergessenwerden (Art. 17 DSGVO).
- **Purge-Routine:** Temporäre OCR-Daten, Cache-Dateien in `tmp/` und personenbezogene Informationen (PII) in Agenten-Logs werden nach **30 Tagen** automatisiert gelöscht.
- **Offline-First:** Es findet kein Datentransfer in externe Clouds statt. Alle Analysen (OCR, LLM, Scheduling) laufen lokal auf der Instanz des Handwerkers.

### 3.2. Pseudonymisierung
Das `AuditLogger`-Modul implementiert eine automatisierte Maskierung von PII.
- **Funktion:** `anonymize_payload` erkennt E-Mails und Namen in Tool-Inputs/Outputs mittels Regex und Heuristiken und ersetzt diese durch Platzhalter, bevor sie dauerhaft im Audit-Trail gespeichert werden.

---

## 4. Security-Architektur (Schutz vor Manipulation)
Schutzmaßnahmen gegen moderne Angriffsvektoren auf KI-Systeme.

### 4.1. Salted Sequence Tags (SST)
Schutz vor **Indirect Prompt Injections** über manipulierte externe Daten (z.B. bösartige E-Mails oder PDFs).
- **Mechanismus:** Jede Tool-Interaktion wird durch eine einmalige Session-ID (Salt) gekapselt.
- **Validierung:** Der `OrchestratorV2` prüft die Integrität der Sequenz (`validate_sequence`) vor der Weiterverarbeitung. Manipulationen im Datenstrom führen zum sofortigen Abbruch der Kette.

### 4.2. Explainable AI (XAI) & Nachvollziehbarkeit
Gemäß Art. 22 DSGVO und dem EU AI Act ist jede automatisierte Entscheidung nachvollziehbar.
- **Reasoning Hash:** Jeder Tool-Aufruf im Audit-Log enthält ein `reasoning`-Attribut, das die logische Herleitung der KI für die Wahl des jeweiligen Werkzeugs dokumentiert.

---

## 5. System-Resilienz
- **Concurrency-Schutz:** Einsatz des `WAL-Mode` (Write-Ahead Logging) in SQLite zur Vermeidung von Datenbank-Deadlocks bei hoher Agenten-Aktivität.
- **Zombie-Hunter:** Graceful Shutdown Routine terminiert alle Hintergrundprozesse (IMAP-Trigger, P2P-Discovery) sauber, um Dateninkonsistenzen zu verhindern.

---
**Prüfvermerk:**
Die technische Implementierung der oben genannten Punkte wurde am 23.02.2026 durch den Lead Architect verifiziert und erfolgreich durch den `ChaosSeeder` Red-Teaming-Test validiert.
