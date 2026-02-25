# KUKANILEA Lizenzierungsworkflow

Dieses Dokument beschreibt den Prozess zur Erstellung hardwaregebundener Lizenzen für KUKANILEA v1.5.0 Gold.

## Sicherheit

- **Privater Schlüssel:** Der RSA-4096 Private Key (`internal_vault/license_priv.pem`) darf niemals das sichere Terminal (z.B. ZimaBlade) verlassen.
- **Signatur:** Lizenzen werden mittels RSA-PSS Padding signiert, um Manipulationen auszuschließen.

## Workflow zur Lizenzerstellung

1. **HWID erhalten:** Der Kunde sendet seine 64-stellige Hardware-ID (SHA-256 Hash).
2. **Generierung starten:** Führen Sie das Skript im Root-Verzeichnis aus:
   ```bash
   python3 scripts/generate_license.py --hwid <KUNDEN_HWID> --days 365 --features all
   ```
3. **Auslieferung:** Die Datei `license.kukani` wird generiert und dem Kunden per E-Mail zugestellt.
4. **Archivierung:** Ein Backup der Lizenz und des Hashes wird automatisch in `internal_vault/issued_licenses.db` gespeichert.

## Features

Verfügbare Feature-Flags:
- `vision_pro`: Erweiterte PicoClaw-Bildanalyse.
- `voice_command`: Vollständige Sprachsteuerung.
- `multi_user_10`: Unterstützung für bis zu 10 Benutzer.
- `gobd_audit_ready`: Revisionssichere Archivierung.
