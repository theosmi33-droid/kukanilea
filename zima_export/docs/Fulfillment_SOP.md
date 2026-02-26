# KUKANILEA Enterprise: Standard Operating Procedure (SOP)
## Dokument: FULFILLMENT & LICENSING (Version 1.6.0)

Dieses Protokoll dient der fehlerfreien Auslieferung von KUKANILEA Enterprise Lizenzen. Jede Abweichung von diesem Prozess gefährdet die Sicherheit des Geschäftsmodells.

---

### PHASE 1: AUFTRAGSEINGANG (INPUT)
Sobald ein Partner oder Pilotkunde eine Lizenz bestellt, muss er den **Activation Code** übermitteln.

1. **Code-Validierung:** Prüfe den Code auf das Format `KUK-XXXX-XXXX-XXXX-XXXX`.
2. **Kunden-Stammblatt:** Lege einen Ordner für den Kunden an (z.B. `customers/2026/Maler_Betrieb_GmbH/`).
3. **Hardware-Bindung:** Kopiere den Activation Code in eine Textdatei `hwid.txt` in diesem Kundenordner.

---

### PHASE 2: AIR-GAPPED SIGNING (DER COLD-STORAGE PROZESS)
*Maxim: Der Private-Key berührt niemals dauerhaft die Festplatte deines Arbeitsrechners.*

1. **USB-Stick einstecken:** Schließe den verschlüsselten Master-Key USB-Stick an.
2. **Mounting:** Navigiere im Terminal auf den USB-Stick (z.B. `/Volumes/KUKANI_MASTER/keys/`).
3. **Lizenz-Schmiede:** Führe den Generator-Befehl aus, während der Pfad zum Private-Key auf den USB-Stick zeigt:
   ```bash
   python3 scripts/ops/generate_enterprise_license.py [CODE] "[Kundenname]"
   ```
   *Hinweis: Der Pfad zum Key muss im Skript ggf. per Environment-Variable `KUKANI_KEY_PATH` angepasst werden.*
4. **USB-Stick sicher entfernen:** Sofort nach der Generierung der `license.json` den Stick unmounten und physisch entfernen.

---

### PHASE 3: QUALITÄTSSICHERUNG (VERIFIKATION)
Bevor die Datei den Versandschalter verlässt:

1. **Fingerprint-Check:** Öffne die generierte `license.json` mit einem Texteditor.
2. **Abgleich:** Stelle sicher, dass das Feld `"device_fingerprint"` mit dem vom Kunden gesendeten Code übereinstimmt.
3. **Ablaufdatum:** Verifiziere, dass `"expiry"` korrekt auf 365 Tage (oder den vereinbarten Zeitraum) in der Zukunft gesetzt ist.

---

### PHASE 4: PAKETIERUNG & VERSAND (OUTPUT)
Erstelle eine E-Mail oder einen gesicherten Download-Link für den Partner mit folgendem Inhalt:

1. **Die Lizenz:** `license.json` (Umbenannt in `license.json`, falls der Generator sie spezifisch benannt hat).
2. **Das Welcome-Kit:** `WELCOME_KIT.pdf` (aus `zima_export/docs/`).
3. **Das Pitch-Deck:** `PITCH_DECK_HANDWERK.pdf` (für den Endkunden-Verkauf durch den Partner).
4. **Der Installer:** Download-Link zur aktuellen `KUKANILEA.dmg`.

---

### PHASE 5: ABSCHLUSS & ARCHIVIERUNG
1. **CRM-Update:** Markiere den Auftrag als "Fulfilled".
2. **Backup:** Sichere die `license.json` (OHNE Private-Key!) in deinem verschlüsselten Kundenarchiv, um bei Verlust des Kundengeräts schnell Ersatz leisten zu können.

---
**GEFAHRENHINWEIS:**
Sollte die Datei `kukanilea_private.key` jemals in einer E-Mail oder einem Cloud-Backup auftauchen, gilt der Master-Key als kompromittiert. In diesem Fall muss der Public-Key in der gesamten KUKANILEA-Flotte per Zwangsupdate getauscht werden.
