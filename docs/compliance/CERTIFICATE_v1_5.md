# 🛡️ KUKANILEA v1.5.0 Gold – GoBD & DSGVO Compliance Zertifikat

**Ausstellungsdatum:** 24. Februar 2026  
**Software-Version:** 1.5.0-gold  
**Zustand:** Production Ready / GOLD  
**Gültig für Hardware-ID:** `52aedd3f1e23bd669f73d8cd17e4e837f113a50fe4c97d414ba00c41bd4a74d0`

---

## 1. Zusammenfassung der Sicherheitsmerkmale

KUKANILEA wurde nach den Prinzipien **Privacy by Design** und **Offline-First** entwickelt. Die Software erfüllt die Anforderungen der DSGVO (EU-Datenschutz-Grundverordnung) und unterstützt die Einhaltung der GoBD (Grundsätze zur ordnungsmäßigen Führung und Aufbewahrung von Büchern, Aufzeichnungen und Unterlagen in elektronischer Form).

## 2. Datenschutz (DSGVO)

- **100% Offline-Betrieb:** Es findet keine Datenübertragung in die Cloud statt. Alle personenbezogenen Daten (PII) verbleiben ausschließlich auf der Hardware des Nutzers.
- **Hardware-Bindung:** Lizenzen sind kryptografisch an die Hardware-ID (RSA-4096) gebunden. Dies verhindert unbefugte Vervielfältigung und schützt Kundendaten vor unkontrollierter Verbreitung.
- **Datenminimierung:** Es werden nur Daten erhoben und verarbeitet, die für den Betrieb der Handwerks-Software zwingend erforderlich sind.
- **Support-Datenschutz:** Diagnose-Exporte für den Support werden automatisch sanitiert (Maskierung von Namen, E-Mails, IBANs) und verschlüsselt, bevor sie das Gerät verlassen.

## 3. Revisionssicherheit (GoBD)

- **Manipulationsschutz:** Alle steuerrelevanten Dokumente werden mit SHA-256 Hashing gegen nachträgliche Änderungen gesichert.
- **Traceability:** Das System protokolliert alle relevanten Statusänderungen lokal in der `app.log`.
- **Archivierung:** Die lokale SQLite-Datenbank nutzt den Write-Ahead-Logging (WAL) Modus für maximale Datenintegrität und Ausfallsicherheit.

## 4. Technischer Fingerabdruck

- **Hashing-Algorithmus:** SHA-256
- **Verschlüsselung (Support-Dumps):** RSA-4096 (Hybrid mit AES-256)
- **Lizenz-Signierung:** Ed25519 (Digital Signature)
- **Modelle:** Offline PicoClaw (LLM) & Moondream2 (Vision)

---

**Bestätigt durch:**  
*KUKANILEA Lead Architect / Release Captain*  
*ZimaBlade Deployment Unit #1*
