# KUKANILEA Release Runbook (v1.5.0 Gold)

## 1. Vorbereitung
- Stelle sicher, dass `internal_vault/license_priv.pem` vorhanden ist.
- NAS `/KUKANILEA-ENDKUNDE` (ZimaBlade) mounten.

## 2. Build Prozess (macOS)
1. Zertifikate in der Keychain prüfen.
2. `./scripts/build/bundle_macos.sh` ausführen.
3. Notarisierung abwarten: `xcrun notarytool log <ID>`.

## 3. Lizenz-Generierung für Kunden
1. HWID vom Kunden erfragen.
2. `python scripts/generate_license.py --hwid <ID>`
3. Die Lizenz wird automatisch auf das NAS gespiegelt und lokal als `license.kukani` gespeichert.

## 4. Distribution
- DMG aus `dist/final/` an Kunden versenden.
- Lizenz aus dem NAS-Ordner des Kunden bereitstellen.
