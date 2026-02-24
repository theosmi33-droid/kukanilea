# KUKANILEA Internal Licensing & Key Management

## 1. RSA Master Keys
Die Sicherheit von KUKANILEA v1.5.0 basiert auf einem 4096-bit RSA Schlüsselpaar. 

- **Private Key (`license_priv.pem`):** Befindet sich im `internal_vault/`. Dieser Schlüssel darf **niemals** das Unternehmen verlassen oder in das Git-Repository eingecheckt werden. Er ist zusätzlich mit einem Passwort verschlüsselt.
- **Public Key (`license_pub.pem`):** Befindet sich in `app/core/certs/`. Dieser wird mit jeder App-Instanz ausgeliefert und dient zur mathematischen Verifizierung der Lizenz.

## 2. Lizenz-Generierung
Um eine neue Kundenlizenz zu erstellen:
1. Erfragen Sie die Hardware-ID (HWID) beim Kunden.
2. Führen Sie den Generator aus:
   ```bash
   python scripts/generate_license.py --hwid <KUNDEN_HWID> --days 365 --features "vision_pro,voice_extra"
   ```
3. Senden Sie die resultierende `license.kukani` an den Kunden.

## 3. Desaster Recovery
Falls der Private Key verloren geht, können **keine neuen Lizenzen** mehr ausgestellt werden. Vorhandene Instanzen funktionieren zwar weiter, aber Upgrades oder neue Installationen sind unmöglich.
**Sichern Sie den `internal_vault/` offline auf einem verschlüsselten Medium.**
