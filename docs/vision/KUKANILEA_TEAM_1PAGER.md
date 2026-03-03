# 📋 KUKANILEA – TEAM-ARBEITSANWEISUNG (1-Seiter)

**Projekt:** KUKANILEA Sovereign 11 Ecosystem  
**Launch:** April 2026 (6 Wochen)  
**Ziel:** Unkopierbares, lokales Business-OS für Handwerk

---

## ⚡ DIE 6 KRITISCHEN P0-BLOCKER (SOFORT FIXEN!)

```bash
# 1. Logger kaputt (GoBD tot)
python -m py_compile app/logging/structured_logger.py
# Fix Syntaxfehler, dann smoke-test

# 2. DB-Migrations nicht verdrahtet (Memory/Queue crashen)
# Entscheidung: auth.sqlite3 = Identity + Memory + Queue
# Migrations idempotent beim Boot ausführen

# 3. RAG-Pipeline: Counter fehlt
# app/core/rag_sync.py: from collections import Counter

# 4. Tailwind CDN raus (Zero-CDN-Regel)
grep -r "local-tailwind-asset.invalid" app/ 
# Alle Treffer löschen

# 5. DeepL offline (Offline-First)
# Feature-Flag: ENABLE_EXTERNAL_APIS=false (default)

# 6. CSP härten
# Kein unsafe-inline mehr, Nonce/Hash verwenden
```

**DoD:** Alle 6 fixes committed, pytest grün, keine Regressionen.

---

## 🏛️ SOVEREIGN 11 SHELL (2 Wochen)

**Was:** Minimalistisches UI mit exakt 11 Tools, White-Mode, <150ms Load.

**Week 1: Foundation**
```bash
# Fonts & Icons lokal laden
mkdir -p app/static/fonts app/static/icons
# Inter-Regular/Medium/SemiBold.woff2 + sprite.svg (11 Icons)

# sovereign-shell.css erstellen
# White-Mode forced, 8pt-Grid, WCAG AA, Sidebar 240px
```

**Week 2: Integration**
```bash
# Route-Stubs für alle 11 Tools (keine 404)
# Scope-Requests generieren & ausfüllen (je 30 Min)
# Overlap auflösen (Aufgaben vs Projekte trennen)
# Patches anwenden (einer nach dem anderen)
```

**DoD:** Alle 11 Routes → 200, Zero CDN, <150ms Load, pytest grün.

---

## 🤖 llmfit-KI-SYSTEM (3 Wochen)

**Was:** Hardware-adaptive KI + Prompt-Injection-Guard + 60-Tage-Cleanup.

**Week 1: llmfit**
```bash
# Ollama + Modelle installieren
ollama pull gemma:2b      # <8GB RAM
ollama pull llama3.2:7b   # >8GB RAM

# llmfit in Bootstrap integrieren
# Hardware-Check → Modell-Empfehlung → Auto-Download
```

**Week 2: Guardrails**
```python
# app/ai/guardrails.py
# Blocke: SQL-Injection, XSS, Command-Injection, Prompt-Injection
# Semantic-Guard mit LLM (erkennt "Ignore all previous...")
```

**Week 3: Memory + Cleanup**
```sql
-- Pro Tenant eigene DB: instance/memory/<tenant_id>.db
-- Cleanup-Job: DELETE WHERE created_at < NOW()-60d AND importance < 8
-- VACUUM täglich um 3 AM
```

**DoD:** llmfit funktioniert, Guardrails blocken OWASP-Patterns, Cleanup läuft.

---

## 🔐 LIZENZ-SYSTEM (1 Woche)

**Was:** Excel auf NAS steuert Lizenzen, automatische Sperrung bei Nichtzahlung.

**Excel-Struktur (auf smb://192.168.0.2/KUKANILEA-ENDKUNDE/):**
```
Mandant-ID | Firma | Lizenz-Key | HW-ID | Status | Gültig bis | Notizen
M001       | Müller| ABC-123... | FP001 | AKTIV  | 2027-12-31 | -
M002       | Bau   | DEF-456... | FP002 | GESPERRT| 2026-06-30| Rechnung offen
```

**Daily-Check (4 AM):**
```python
# app/services/license_checker.py
# Connect SMB → Read Excel → Check Status
# If GESPERRT → Lock-Screen + Audit-Log
# Offline-Grace: 7 Tage ohne NAS = OK, Tag 8 = Lock
```

**DoD:** Lock-Screen bei GESPERRT, Offline-Grace funktioniert, SMB stabil.

---

## 💾 BACKUP-STRATEGIE (1 Woche)

**Was:** Verschlüsselte, komprimierte Backups auf NAS (4TB), mandantengetrennt.

**Backup-Job (3 AM täglich):**
```bash
#!/bin/bash
# scripts/ops/backup_to_nas.sh

# 1. Dump DB
sqlite3 instance/kukanilea.db .dump > /tmp/db_dump.sql

# 2. Compress (zstd Level 19 = 10:1 Ratio)
tar -cf - instance/ | zstd -19 -T0 -o /tmp/backup.tar.zst

# 3. Encrypt
openssl enc -aes-256-cbc -salt -pbkdf2 \
  -in /tmp/backup.tar.zst \
  -out /tmp/backup.tar.zst.enc \
  -pass pass:$BACKUP_PASSWORD

# 4. Upload to NAS
cp /tmp/backup.tar.zst.enc /mnt/kukanilea_nas/M001/

# 5. Cleanup (>30 days old)
find /mnt/kukanilea_nas/M001/ -mtime +30 -delete
```

**DoD:** Backup läuft täglich, 10:1 Kompression, Restore-Test erfolgreich.

---

## 🌐 MESH-NETZWERK (Bereits vorhanden, nur aktivieren)

**Was:** Alle Firmenrechner kommunizieren P2P, offline-fähig.

**Aktivierung:**
```bash
# Mesh-Identity existiert bereits (Ed25519 Keys)
# Sync-Engine: CRDT-basiert für Tasks/Projekte/Kalender
# Discovery: mDNS (lokal) + Tailscale (remote)
```

**DoD:** Rechner finden sich, Sync funktioniert, keine Konflikte.

---

## 📅 TIMELINE (6 Wochen)

```
Woche 1-2: P0-Bugs + Sovereign 11 Shell
Woche 3-5: llmfit-KI-System
Woche 6:   Lizenz + Backup
Woche 7-8: Rollout (5 Pilotkunden)
```

---

## 👥 ROLLEN

**Gen (CEO/Lead):** Kunden-Akquise, Vor-Ort-Installation, Schulung, NAS-Admin  
**Core-Team:** P0-Bugs, Shell, Integration, NAS-Skripte  
**Domain-Devs:** Kern-Logik in Worktrees, API-Summaries, Tests  
**QA:** Smoke-Tests, Dokumentation, Bug-Tracking

---

## ✅ DEFINITION OF DONE

- [ ] Alle 6 P0-Bugs gefixt
- [ ] Sovereign 11 Shell: 11 Routes, Zero CDN, <150ms
- [ ] llmfit: Auto-Setup, Guardrails, 60d-Cleanup
- [ ] Lizenz: Excel-Check, Lock-Screen, Offline-Grace
- [ ] Backup: Täglich, verschlüsselt, 10:1 Ratio
- [ ] Mesh: P2P-Sync funktioniert
- [ ] 5 Pilotkunden: Installiert, geschult, Feedback
- [ ] Tests: pytest grün, E2E grün, Load-Test grün

---

## 🚨 HARD RULES (DO/DON'T)

**DO:**
- P0 zuerst fixen (nichts anderes!)
- Tests nach jedem Patch laufen lassen
- Scope-Requests für Shared-Core nutzen
- White-Mode enforced, 8pt-Grid
- Offline-First by default

**DON'T:**
- Keine CDNs (Zero-CDN-Regel)
- Keine externen APIs ohne Opt-in
- Keine Dark-Mode-Option
- Keine Shared-Core-Edits ohne Scope-Request
- Keine >15 Wörter Quotes (Copyright!)

---

**LAUNCH: KW 15 (14.-18. April 2026) 🚀**

**Drucke dieses Blatt aus. Klebe es an die Wand. Lebe danach.** ✅
