# 🛡️ KUKANILEA v1.5.0 GOLD – COMPLIANCE MANIFEST

**Status:** PRODUCTION READY / GOLD SEAL  
**Datum:** 24. Februar 2026  
**Hardware-ID:** `52aedd3f1e23bd669f73d8cd17e4e837f113a50fe4c97d414ba00c41bd4a74d0`

## 1. Übersicht
Dieses Manifest zertifiziert die Konformität der KUKANILEA v1.5.0 Gold Software mit den geltenden Datenschutz- und Revisionsstandards für den Offline-Einsatz im Handwerk.

## 2. Sicherheits-Architektur (GOLD Standard)
- **Offline-First (CRA Compliance):** Keine Cloud-Anbindung. Alle KI-Berechnungen (PicoClaw/Moondream2) erfolgen lokal.
- **RSA-4096 Licensing:** Kryptografische Bindung der Software an die Hardware-ID des Endgeräts.
- **SHA-256 Hashing:** Alle steuerrelevanten Dokumente werden revisionssicher gehasht, um GoBD-Konformität zu gewährleisten.
- **Support Privacy:** Der Diagnostic Exporter maskiert PII (Namen, E-Mails, IPs) automatisch und verschlüsselt den Dump hybrid (RSA-OAEP + AES-256).

## 3. Datenintegrität & Revisionssicherheit (GoBD)
- **Persistence:** Die lokale SQLite-Datenbank nutzt den WAL-Modus zur Vermeidung von Datenverlust bei Stromausfall.
- **Auto-Purge:** Einstellbare Löschfristen für DSGVO-konforme Datenbereinigung nach Projektende.
- **Audit-Log:** Lokale Erfassung kritischer Systemereignisse in der `app.log`.

## 4. Hardware-Fingerabdruck
Zertifiziert für das Gerät mit der Hardware-ID: `52aedd3f1e23bd669f73d8cd17e4e837f113a50fe4c97d414ba00c41bd4a74d0`.

---
**Freigegeben durch:**  
*KUKANILEA Release Captain*
