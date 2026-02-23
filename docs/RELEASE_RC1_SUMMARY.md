# KUKANILEA RC1 - Release Candidate Summary (Go-Live Readiness)

**Datum:** Montag, 23. Februar 2026  
**Status:** GRÜN (Alle Sicherheitstests bestanden)  
**Zielgruppe:** Lokale Handwerksbetriebe (v1.0 Commercial Rollout)

## 1. Hardening & Security (Done)

- **Prompt Injection Defense:** Implementierung von **Salted Sequence Tags**. Alle User-Inputs werden mit kryptografischen 16-Byte-Salts umschlossen (`<salt_hex>...<salt_hex>`). Dies verhindert das Ausbrechen aus dem Kontext durch XML-Tag-Guessing.
- **Test-Verifizierung:** 3/3 spezialisierte Security-Tests in `tests/security/test_salted_inference.py` erfolgreich.
- **SQL-Sicherheit:** Datenbankzugriffe sind auf `sqlglot`-validierte SELECT-Statements beschränkt.

## 2. Hardware-Autodetektion (Done)

- **Multi-Plattform Performance:** Neues Modul `app/core/hardware.py`.
- **Apple Silicon:** Erkennt M-Chips und optimiert VRAM-Zuweisung (Metal).
- **Windows/NVIDIA:** Erkennt CUDA-Kerne via `nvidia-smi` im Hintergrund (Silent Mode, kein Konsolen-Popup).
- **Fallback:** Intelligente CPU-Skalierung für ältere Hardware.

## 3. "One-Click" User Experience (Done)

- **Ollama Integration:** Die Anwendung startet den lokalen Ollama-Backend-Service jetzt automatisch im Hintergrund (`app/ollama_runtime.py`).
- **Graceful Shutdown:** Beim Schließen von KUKANILEA wird der verwaltete Ollama-Prozess sauber beendet, um Ressourcen zu sparen.

## 4. Distribution & Build-Prozess

### macOS (Notarized App)
Das Build-Skript erzeugt ein signiertes `.app` Bundle und ein `.dmg` Disk Image.
- **Befehl:** `scripts/build/bundle_macos.sh`
- **Notarisierung:** Erfordert Apple Developer Zertifikat.

### Windows (Setup Installer)
Vollständiger NSIS-Installer-Pfad implementiert.
- **Befehl:** `scripts/build/installer_windows.ps1`
- **Besonderheit:** Inkludiert alle KI-Abhängigkeiten (`chromadb`, `sentence-transformers`) als Hidden-Imports für volle RAG-Funktionalität in der Standalone-EXE.

## 5. Nächste Schritte

1. **macOS Signierung:** Finaler Durchlauf der `codesign` Routine mit dem offiziellen Tophandwerk-Zertifikat.
2. **Beta-Test:** Auslieferung der `KUKANILEA_Setup_v1.0.0.exe` an die erste Testgruppe.

---
**Freigabe durch:** Gemini CLI (Senior AI Architect)
