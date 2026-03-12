# Lokale Installation – erster Diagnosepfad

Ziel: Ein **reproduzierbarer Erstcheck** für lokale Installationen, wenn unklar ist, ob die Instanz sauber startfähig ist.

## Trigger

Nutze diesen Pfad, wenn mindestens einer der Punkte zutrifft:
- App startet lokal nicht stabil.
- `/` oder Kernrouten antworten nicht wie erwartet.
- Nach Setup/Update soll ein schneller Sicherheits- und Betriebs-Baseline-Check laufen.

## 1) Exakter Befehl

```bash
scripts/ops/first_diagnose_local.sh
```

Optional mit festem Interpreter:

```bash
PYTHON=".venv/bin/python" scripts/ops/first_diagnose_local.sh
```

## 2) Erwartbares Ergebnis

- Exit Code `0`: Baseline passt (Guardrails + schneller Healthcheck).
- Exit Code ungleich `0`: Diagnose fehlgeschlagen; das Skript gibt den nächsten Schritt direkt aus.

## 3) Nächster Schritt bei Fehler

Wenn der Erstcheck fehlschlägt, sofort den Vollcheck ausführen:

```bash
PYTHON=".venv/bin/python" scripts/ops/healthcheck.sh --strict-doctor
```

Damit wird derselbe Pfad mit strikter Umgebungskontrolle (Doctor + vollständige Gates) reproduzierbar vertieft.
