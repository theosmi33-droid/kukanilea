# Gemini CLI Fallback (Notfall)

## Ziel
Schneller Wechsel in den Terminal-Workflow, falls VS Code/Gemini UI blockiert.

## Voraussetzungen
- `gemini` installiert (`gemini -v`)
- OAuth Personal Login aktiv (`~/.gemini/settings.json`)
- Modell: `gemini-3-flash-preview` (kostenfrei)

## Schnellbefehle
- `gflash`
  - Startet Gemini CLI direkt mit Flash-Modell im aktuellen Ordner.
- `gkuka`
  - Wechselt nach `/Users/gensuminguyen/Kukanilea/kukanilea_production` und startet Gemini CLI mit Flash-Modell.
- `gkprompt "<dein prompt>"`
  - Führt einen einmaligen Prompt headless im KUKANILEA-Root aus.
- `gkufallback [args]`
  - Nutzt `/scripts/ops/gemini_fallback.sh` (für Ops/CI).

## Beispiel
```bash
gkprompt "Lies Shared-DB und gib aktive Direktiven aus"
```

## Fehlerbilder
- Quota/429:
  - Modell bleibt Flash; kurz warten und erneut senden.
- Projekt-Dialog in VS Code:
  - `geminicodeassist.project` leer halten, Individuals-Modus nutzen.

## Verifikation
```bash
gemini -v
gkprompt "antworte nur mit ok"
```
