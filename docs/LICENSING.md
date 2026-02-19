# Licensing

Stand: 2026-02-19

## Modell
- Trial: 14 Tage (konfigurierbar)
- Lizenz: signierte lokale Lizenzdatei (`license.json`)
- Online-Validierung: optional, standardmaessig alle 30 Tage
- Grace: 30 Tage bei nicht erreichbarer Validierung
- Enforcement: Nach Trial/Lizenzablauf oder invalidem Remote-Status laeuft die Instanz in `READ_ONLY`

## Aktivierung
1. Als `ADMIN` oder `DEV` einloggen.
2. Seite `/license` oeffnen.
3. Signiertes Lizenz-JSON einfuegen und speichern.
4. Die Instanz laedt den Laufzeitstatus neu (`PLAN`, `READ_ONLY`, `LICENSE_REASON`).

Hinweis:
- Aktivierung ist auch im Read-only-Modus erlaubt (damit ein abgelaufener Trial ohne CLI wieder freigeschaltet werden kann).

## Laufzeitverhalten
- Schreiboperationen (`POST/PUT/PATCH/DELETE`) werden bei `READ_ONLY` global mit `403` geblockt.
- Leseoperationen bleiben verfuegbar.
- UI zeigt den aktuellen Lizenzstatus und den Grund (`LICENSE_REASON`).

## Online-Validierung / Grace
- Wenn `KUKANILEA_LICENSE_VALIDATE_URL` gesetzt ist, validiert die App den signierten Payload periodisch.
- Ist der Endpoint voruebergehend nicht erreichbar, wird das Grace-Fenster aus dem lokalen Cache genutzt.
- Nach Ablauf von Grace wird auf `READ_ONLY` gewechselt.

## Relevante Umgebungsvariablen
- `KUKANILEA_LICENSE_PATH`
- `KUKANILEA_TRIAL_PATH`
- `KUKANILEA_TRIAL_DAYS`
- `KUKANILEA_LICENSE_VALIDATE_URL` (Alias: `LICENSE_SERVER_URL`)
- `KUKANILEA_LICENSE_VALIDATE_TIMEOUT_SECONDS`
- `KUKANILEA_LICENSE_VALIDATE_INTERVAL_DAYS`
- `KUKANILEA_LICENSE_GRACE_DAYS`
- `KUKANILEA_LICENSE_CACHE_PATH`
