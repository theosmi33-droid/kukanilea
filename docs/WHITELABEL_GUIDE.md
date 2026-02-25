# KUKANILEA – White-Labeling & Partner Guide

Dieser Guide beschreibt, wie Sie KUKANILEA an Ihre eigene Marke anpassen und für Ihre Kunden paketieren können.

## 1. Visuelles Branding
KUKANILEA nutzt ein zentrales Design-System in `app/web.py` (HTML_BASE) und `static/css/`.

### Farben & Fonts
Passen Sie die CSS-Variablen in `HTML_BASE` an:
- `--accent`: Ihre Primärfarbe (z.B. `#ea580c` für Orange).
- `--bg`: Hintergrundfarbe.
- `--font-sans`: Ihre Haus-Schriftart.

### Logos & Icons
Ersetzen Sie folgende Dateien in `app/static/img/`:
- `logo.svg`: Das Hauptlogo links oben.
- `favicon.ico`: Browser-Icon.
- `app-icon.png`: Icon für den PWA-Install und die Desktop-Verknüpfung.

## 2. Produktname & Identität
Der Name "KUKANILEA" kann global geändert werden.

1. **Konfiguration:** Setzen Sie die Umgebungsvariable `PRODUCT_NAME="IhrName"`.
2. **KI-Persona:** Bearbeiten Sie `instance/identity/SOUL.md`. Ändern Sie dort die Identität des "Digitalen Meisters" auf Ihre spezifische Branche (z.B. "Digitaler Malermeister").

## 3. Partner-Lizenzschlüssel
Als Partner können Sie eigene RSA-Schlüsselpaare generieren, um Lizenzen unabhängig vom Haupt-Repository auszustellen.
- Platzieren Sie Ihren `license_pub.pem` in `app/core/certs/`.
- Nutzen Sie das `license_provisioning` API-Modul für automatisierte Freischaltungen.

## 4. Paketierung (Installer)
Passen Sie das Skript `scripts/bundle_macos.sh` an:
- Ändern Sie `APP_NAME="IhreMarke"`.
- Integrieren Sie Ihre eigenen Template-Overrides im `--add-data` Bereich von PyInstaller.

---
*KUKANILEA Partner Support | Stand: Februar 2026*
