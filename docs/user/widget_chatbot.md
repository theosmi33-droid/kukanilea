# Widget Chatbot (AI Companion)

## Was ist neu
- Globales Floating-Widget unten rechts auf allen Layout-Seiten.
- Kontextbewusstsein: Der Bot kennt die aktuelle Route (z. B. `/upload`, `/time`).
- Quick Actions je Seite (z. B. `Extrahiere Daten` auf Upload-Seiten).
- Overlay ist minimierbar und in der Groesse anpassbar.
- Zustand bleibt beim Seitenwechsel erhalten (open/minimiert/Groesse/unread).

## Nutzung
1. Auf den runden `KI`-Button klicken.
2. Nachricht eingeben oder Quick Action anklicken.
3. Bei schreibenden Aktionen erscheint ein Confirm-Gate (`Ja, ausfuehren`).

## Sicherheitslogik
- Keine stillen Aktionen.
- Schreibende Agent-Aktionen werden immer vor Ausfuehrung bestaetigt.
- Prompt-Inhalte werden als User-Input getrennt vom Kontext verarbeitet.

## Performance
- Widget-JS wird non-blocking geladen.
- Auf schwacher Hardware wird ein kleineres lokales Modellprofil verwendet.
- Bei minimiertem/geschlossenem Overlay zeigt ein Badge neue Antworten an.
