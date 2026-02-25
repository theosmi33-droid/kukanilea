# KUKANILEA Enterprise: Fulfillment-Checkliste
## Prozess für die Auslieferung an Pilotkunden & Partner

Diese Checkliste stellt sicher, dass jede KUKANILEA-Instanz korrekt konfiguriert, signiert und betriebsbereit übergeben wird.

### Phase 1: Hardware-Vorbereitung (ZimaBlade / Mac)
- [ ] OS installiert und gehärtet (keine unnötigen offenen Ports).
- [ ] Ollama installiert und Basis-Modelle gepullt (`llama3.2:1b`, `qwen2.5:0.5b`).
- [ ] KUKANILEA-App im Programme-Ordner/Autostart hinterlegt.

### Phase 2: Onboarding & HWID-Erfassung
- [ ] Kunde startet das System zum ersten Mal.
- [ ] Kunde übermittelt den **Activation Code** (z.B. `KUK-E8A5-...`).
- [ ] HWID in der internen Kundendatenbank registrieren.

### Phase 3: Lizenz-Generierung (Backoffice)
- [ ] Internes Tool aufrufen: `python scripts/ops/generate_enterprise_license.py <HWID> "<Kundenname>"`
- [ ] Gültigkeit prüfen (Standard: 365 Tage).
- [ ] Generierte `license_<Name>.json` für den Versand vorbereiten.

### Phase 4: Auslieferung & Aktivierung
- [ ] `license.json` an den Kunden senden (E-Mail oder verschlüsselter Download).
- [ ] Welcome-Kit (`WELCOME_KIT.md`) als PDF beifügen.
- [ ] Bestätigung vom Kunden einholen, dass der Status "Plan: ENTERPRISE" aktiv ist.

### Phase 5: Day-2 Ops (Nachträglich)
- [ ] Cronjob für `maintenance_daemon.sh` (03:00 Uhr) verifiziert.
- [ ] Erstes lokales Backup durch den Kunden initiiert.

---
**Maxim:** Jeder Kunde ist eine Festung. Keine Kompromisse bei der Datensouveränität.
