# Release Test Protokoll (v1.5.0-Gold)

**Datum:** 2026-02-24
**Version:** v1.5.0-Gold
**Tester:** System Architect / Automation

## Test 1: Systemstart ohne Lizenz
- **Ziel:** Verifikation des Read-Only-Modus.
- **Aktion:** Installation von KUKANILEA auf einer frischen VM ohne `license.bin` im Installationsverzeichnis.
- **Beobachtung:**
  - Der `LicenseValidator` erkennt die fehlende Datei (`license.bin fehlt`).
  - Das System blockiert jegliche Agent-Aufrufe (Mutationen) und gibt eine Warnung aus: `System im Read-Only Modus. Bitte gültige Lizenz einspielen.`
  - Ein manueller Versuch, einen CRM-Kontakt anzulegen, wird blockiert.
- **Status:** ✅ BESTANDEN

## Test 2: Systemstart mit gültiger Hardware-Lizenz
- **Ziel:** Feature-Freischaltung durch RSA-signierte Hardware-Lizenz.
- **Aktion:** Ausführung von `scripts/generate_license.py --hwid <VM-MAC>` und Hinterlegung der generierten `license.bin`.
- **Beobachtung:**
  - Der `LicenseValidator` verifiziert die RSA-Signatur und gleicht die `hardware_id` der Payload mit der aktuellen MAC-Adresse ab.
  - Das System bootet erfolgreich. Alle Schreib- und Lese-Vorgänge (Tasks, CRM, Agent-Chat) stehen uneingeschränkt zur Verfügung.
- **Status:** ✅ BESTANDEN

## Test 3: PicoClaw-Vision & Graceful Degradation
- **Ziel:** Latenz-Test der PicoClaw-Extraktion und Ausfall-Sicherheit.
- **Aktion:** Upload eines validen Typenschild-Fotos sowie einer korrupten (bösartigen) Bilddatei.
- **Beobachtung (Valides Bild):**
  - PicoClaw extrahiert Seriennummer und Hersteller aus dem Bild via spezialisierter OCR.
  - Gesamtdauer des Inferenz-Vorgangs: `< 500ms`.
  - Der Output wurde korrekt mit Salted Sequence Tags (SST) gewrappt.
- **Beobachtung (Fehlerhaftes Bild):**
  - PicoClaw schlägt sicher fehl.
  - Der Orchestrator triggert den Moondream2-Fallback (sofern konfiguriert). Wenn Moondream2 via Hardware-Detektion auf < 8GB RAM Maschinen deaktiviert ist, gibt das System eine sichere Warnung aus und degradet graceful.
- **Status:** ✅ BESTANDEN

## Gesamtergebnis
Alle Kriterien der Zero-Error-Policy, der Lizenzierung und der PicoClaw-Integration wurden erfolgreich validiert.
Freigabe für Release: **v1.5.0-Gold** erteilt.
