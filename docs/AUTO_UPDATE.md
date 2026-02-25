# Auto-Update System für KUKANILEA v1.5.0 Gold

Dieses Dokument beschreibt das integrierte Auto-Update-Modul, das sicherstellt, dass KUKANILEA-Instanzen stets auf dem neuesten Stand bleiben.

## Funktionsweise

1.  **Hintergrund-Check:** KUKANILEA prüft alle 24 Stunden asynchron im Hintergrund, ob auf GitHub ein neues Release verfügbar ist.
2.  **Benachrichtigung:** Wenn ein Update gefunden wird, erscheint im Dashboard ein Banner.
3.  **Manueller Trigger:** Der Benutzer kann über das Banner den Download und die Vorbereitung des Updates starten.
4.  **Download & Verifizierung:** Der Installer (DMG für macOS, MSI für Windows) wird heruntergeladen. Optional wird eine GPG-Signaturprüfung gegen den öffentlichen Schlüssel in `app/certs/update_pub.pem` durchgeführt.
5.  **Installation:**
    *   **macOS:** Das System mountet das DMG und ersetzt die `/Applications/KUKANILEA.app`.
    *   **Windows:** Das MSI wird im Silent-Modus installiert.
6.  **Abschluss:** Das Update wird beim nächsten Start der Anwendung aktiv. Temporäre Installer-Dateien werden automatisch bereinigt.

## Sicherheit

*   **Offline-Fähigkeit:** Der Check erfordert eine Internetverbindung, die eigentliche App-Logik bleibt jedoch davon unberührt.
*   **Signatur:** Nur Releases, die mit dem privaten Master-Key signiert wurden, werden akzeptiert (in Produktion).
*   **Zertifikate:** Der öffentliche Schlüssel `update_pub.pem` ist fest in die App integriert.

## Für Entwickler

### Neues Release signieren
Um ein Release zu signieren, muss eine `.sig`-Datei für das DMG/MSI erstellt werden:
```bash
gpg --detach-sign --armor installer.dmg
```
Laden Sie sowohl die `installer.dmg` als auch die `installer.dmg.asc` (umbenannt zu `.sig`) zu den GitHub-Releases hoch.
