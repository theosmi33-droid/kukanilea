# KUKANILEA v1.5.0 GOLD – PROD READY

Dieses Repository ist für den kommerziellen Rollout von KUKANILEA v1.5.0 Gold (Production Ready) versiegelt.

## 🚀 Schnellstart für den Release

### 1. Pre-Flight Check ausführen
Stelle sicher, dass alle Sicherheits- und Integritätstests auf deinem System bestehen:
```bash
./scripts/release_preflight.py
```

### 2. macOS Build (.dmg)
Um das macOS-Bundle zu erstellen:
```bash
# Erzeugt dist/KUKANILEA.app und dist/KUKANILEA_v1.5.0-gold.dmg
./scripts/build/bundle_macos.sh
```

### 3. Windows Build (Installer)
Die Erstellung erfolgt automatisch via GitHub Actions bei jedem Push auf `main` oder manuell:
- **Lokal (erfordert NSIS):** `powershell .\scripts\build\installer_windows.ps1`
- **CI/CD:** Siehe Tab "Actions" in GitHub.

## 🛡️ Sicherheitsmerkmale (GOLD)
- **RSA-4096 Licensing:** Kryptografische Hardware-Bindung (Offline-Aktivierung).
- **Hybrid-Encrypted Diagnostics:** PII-maskierter Support-Export mit RSA-OAEP & AES-256.
- **GoBD Compliance:** SHA-256 Hashing für alle steuerrelevanten Dokumente.
- **Privacy by Design:** 100% Offline-Betrieb (PicoClaw & Moondream2).

## 📦 Distribution
- Der Installer für Windows befindet sich nach dem Build in `dist/KUKANILEA_Setup_v1.5.0-gold.exe`.
- Die Anwendung installiert sich standardmäßig in `%LOCALAPPDATA%`, um Admin-Abfragen zu vermeiden.

---
**Status:** GOLD RELEASE (PROD READY)
**Freigabe:** 24. Februar 2026
