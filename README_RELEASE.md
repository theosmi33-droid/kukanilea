# KUKANILEA - RC1 Release & Distribution Guide

Dieses Repository ist für den kommerziellen Rollout von KUKANILEA v1.0 (Release Candidate 1) vorbereitet.

## 🚀 Schnellstart für den Release

### 1. Pre-Flight Check ausführen
Stelle sicher, dass alle Sicherheits- und Integritätstests auf deinem System bestehen:
```bash
./scripts/release_preflight.py
```

### 2. macOS Build (.dmg)
Um das macOS-Bundle zu erstellen:
```bash
# Erzeugt dist/KUKANILEA.app und dist/KUKANILEA_v1.0.dmg
./scripts/build/bundle_macos.sh
```

### 3. Windows Build (Installer)
Die Erstellung erfolgt automatisch via GitHub Actions bei jedem Push auf `main` oder manuell:
- **Lokal (erfordert NSIS):** `powershell .\scripts\build\installer_windows.ps1`
- **CI/CD:** Siehe Tab "Actions" in GitHub.

## 🛡️ Sicherheitsmerkmale (RC1)
- **Salted Sequence Tags:** Alle KI-Interaktionen sind kryptografisch gesichert, um Prompt-Injections zu verhindern.
- **Hardware-Autodetektion:** Automatische Optimierung für Apple Silicon (M1-M3) und NVIDIA (CUDA).
- **CRA-Compliance:** Automatisierte CycloneDX SBOM-Generierung bei jedem Build (`dist/evidence/sbom.cdx.json`).

## 📦 Distribution
- Der Installer für Windows befindet sich nach dem Build in `dist/KUKANILEA_Setup_v1.0.0.exe`.
- Die Anwendung installiert sich standardmäßig in `%LOCALAPPDATA%`, um Admin-Abfragen zu vermeiden.

---
**Status:** RC1 READY
**Freigabe:** 23. Februar 2026
