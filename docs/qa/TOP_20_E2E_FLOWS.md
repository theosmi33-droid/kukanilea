# QA Roadmap: Top-20 E2E Flows (Kukanilea)

Diese Flows decken 80% des täglichen Nutzens ab und müssen vor jedem Major-Release ('RC-Gate') fehlerfrei sein.

## 1. CRM & Stammdaten
- [x] Login & Tenant-Wechsel
- [ ] Kunden-Neuanlage & Dubletten-Check
- [ ] Kontakt-Historie (E-Mail, Telefonate)
- [ ] Dokumenten-Upload (PDF, Bilder)

## 2. Angebote & Kalkulation
- [ ] Angebotserstellung (Positionen, Aufschläge)
- [ ] Export als PDF & Versand per E-Mail
- [ ] Konvertierung Angebot -> Auftrag
- [ ] Rabatt-Stufen & Skonto-Logik

## 3. Postfach & Kommunikation
- [ ] IMAP-Synchronisation (Echtzeit)
- [ ] KI-Zuweisung von E-Mails zu Deals
- [ ] E-Mail-Verschlüsselung (PGP/S/MIME)
- [ ] WhatsApp-Integration (Core-Webhook)

## 4. System & Sicherheit
- [ ] Backup & Restore (Fresh Install Test)
- [ ] Automatisches Update (Signed Manifest)
- [ ] Offline-Modus & Re-Sync (IndexedDB)
- [ ] Tenant-Isolation (AuthZ-Cross-Check)

## 5. KI-Automatisierung
- [ ] OCR-Beleglesung (Tesseract/Ollama)
- [ ] Auto-Tagging von Rechnungen
- [ ] Sentiment-Analyse in E-Mails
- [ ] Workflow-Trigger (Event-basierte KI)

## 6. a11y-lite Checks
- [ ] Screenreader-Ansage Statusänderung
- [ ] Tastatur-Fokus-Traversal
