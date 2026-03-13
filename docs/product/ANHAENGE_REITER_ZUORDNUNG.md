# Feste Zuordnung: Anhänge in bestehende KUKANILEA-Reiter

Dieses Dokument ist die verbindliche Integrationsregel für alle neuen Anhänge/Vorbilder.

## Leitregel

**Keine neuen Hauptreiter für neue Ideen.**
Alles wird einem bestehenden Arbeitsraum zugeordnet.
Nur wenn nötig, kommt es dort als **Extra** hinein:

- rechte Assistenzspalte
- Zusatzsektion
- History-/Review-Panel
- Kontextkarte
- Vorschlagsbereich
- Status-/Transparenzpanel

## 1. Feste Zuordnung: Anhänge → bestehender KUKANILEA-Reiter

| Anhang / Vorbild | Zentrale Aussage / USP | Ziel-Reiter in KUKANILEA | Umsetzung in KUKANILEA | Typ |
| --- | --- | --- | --- | --- |
| **Fyxer** | Inbox entlasten, Mails sortieren, Drafts, Follow-ups | **Postfach / Email** | Priorisierung, Zusammenfassung, Key Facts, 3 Antwortvorschläge, Follow-up-Hinweise | Kernfunktion im Reiter |
| **Superhuman Mail** | Fokus, Geschwindigkeit, nur Relevantes sehen | **Postfach / Email** | Wichtigkeitslogik, kompakter Lesemodus, schnelle nächste Aktion | Kernfunktion im Reiter |
| **BARMER-Mail-Screenshot** | Formale Mail mit Frist-/Risikowirkung | **Postfach / Email** | Frist-/Risiko-Hinweise, Warnbadge, „Handlungsbedarf“ | Extra im Reiter |
| **Compa** | WhatsApp/Feldkommunikation → Bericht & To-dos | **Messenger** | Baustellenjournal, Zusammenfassung, To-do-Erkennung, Berichtsentwurf | Kernfunktion im Reiter |
| **WeSpotr** | Weniger Nachfragen, mehr Transparenz | **Messenger** | Transparenzpanel, Status-/Nachweisübersicht, „alles sichtbar“ | Extra im Reiter |
| **BauAI** | Ausschreibungen/Unterlagen schnell verstehen | **Upload / Dokumente** | Dokument verstehen, Ausschreibung analysieren, Review-Vorschläge, Folgeaktionen | Kernfunktion im Reiter |
| **Paperless-Logik** (aus voriger Analyse) | Intake, OCR, Zuordnung, Review | **Upload / Dokumente** | Queue, Review, Metadaten, Vorschläge statt Vollautomatik | Kernfunktion im Reiter |
| **pds** | Software für Handwerk & Bau, mobil, flexibel | **Projekte** + **Dashboard** | handwerksnahe Sprache, betriebliche Übersicht, Projektfokus | UX-/Domänenausbau |
| **Buroo** | Digitale Büroarbeit für Handwerker, Planung, Nachverfolgung | **Dashboard**, **Projekte**, **Aufgaben**, **Kalender**, **Postfach** | Büroassistenz-Hinweise, Angebots-/Lead-/Nachverfolgungslogik | verteilt auf bestehende Reiter |
| **satellite** | Erreichbarkeit, Routing, kein Hardware-Chaos | **Einstellungen** / später **Postfach/Messenger-Kontext** | später Call-/Erreichbarkeitsmodul; jetzt nur als Zukunftsrichtung | Später / vorbereitet |
| **AHITSolutions / StempelKraft** | Mobile, klare Zeiterfassung im Feld | **Zeiterfassung** | große Aktionen, Pause/Fahrt, mobile Klarheit, Foto/GPS-Hinweis | Kernfunktion im Reiter |
| **Memtime** | automatische Timeline / lokaler Activity-Verlauf | **Zeiterfassung** | Zeitgedächtnis, Auto-Timeline, Tagesvorschläge | Extra im Reiter |
| **Rise (privacy-first tasks)** | privat, offline, fokussiert | **Aufgaben** | Fokusmodus, lokale/private Aufgaben, ruhige Priorisierung | Extra im Reiter |
| **Always-On Memory Layer** | Informationen konsolidieren und wiederfinden | **Visualizer** / **Dokumente** / **Postfach-Kontext** | Wissensspeicher, Kontext merken, später Query/Recall | vorbereitet / Extra |
| **MIA-Grafik** | Assistenz verbindet Mail, Kalender, Aufgaben, Dokumente | **keine neue Heimat** → verteilt | Kontextleisten in bestehenden Reitern statt neuer Super-Reiter | Architekturprinzip, kein eigener Reiter |
| **Claude vs Claude Code vs Cowork** | Rollen trennen: Chat, Code, Automationen | **Einstellungen / intern / Dev** | keine Endnutzerfunktion, nur Architektur- und Tooling-Denken | intern |
| **AI-Org-Chart (CEO/CTO/Coder)** | Rollen-/Agentenstruktur | **Einstellungen / intern / Dev** | nicht im Nutzerprodukt, höchstens intern dokumentieren | intern |
| **How to Build AI Agents / Stanford** | RAG, ReAct, Tool-Calling, Guardrails | **keine neue UI-Heimat** | intern für MIA-/Assistenz-Logik, nicht direkt im Frontend | intern |
| **AirLLM** | große Modelle auf kleiner Hardware | **Einstellungen / Admin** | Hardware-/Leistungsmodus, Modellstrategie lokal anpassen | Extra in Settings |
| **Data Analyst Roadmap** | Skill-/Lernlandkarte | **keine Produktfunktion** | nicht direkt übernehmen; höchstens Wissens-/Lernkarte intern | verwerfen für Endnutzer |

## 2. Reiterweise Zielbild für KUKANILEA

### Dashboard / Übersicht
Hier landen Dinge, die **betriebliche Orientierung** geben:

- Büroassistenz-Hinweise aus **Buroo**
- Transparenz / weniger Nachfragen aus **WeSpotr**
- offene Follow-ups aus **Postfach**
- Fristen / nächste Schritte aus **Aufgaben / Kalender**
- kein eigener Büroassistent-Reiter

### Postfach / Email
Hier landen alle Mail-bezogenen Stärken:

- **Fyxer / Superhuman** → Priorisierung, Antwortvorschläge, Fokus
- **BARMER-Beispiel** → Frist-/Risiko-/Wichtigkeitsdarstellung
- rechte Assistenzspalte
- Kontakt-Tags
- Review-before-send
- Feedback nach Versand

### Messenger
Hier landen Feldkommunikation und Baustellenstruktur:

- **Compa** → Journal, Zusammenfassung, To-dos, Berichtsentwurf
- **WeSpotr** → Transparenz, weniger Nachfragen, Nachweislogik
- keine zweite Chat-App, sondern Ausbau des bestehenden Reiters

### Upload / Dokumente
Hier landen Dokumentverständnis und Intake-Disziplin:

- **BauAI** → Ausschreibung / Dokument verstehen
- **Paperless-Prinzip** → Queue, Review, Zuordnung, Metadaten
- später Fristen / Folgeaktionen / Projektbezug
- keine neue Dokumenten-KI-App daneben

### Zeiterfassung
Hier landen zwei Stränge:

- **StempelKraft / AHITSolutions** → mobile Klarheit, große Aktionen, Feldnutzung
- **Memtime** → Zeitgedächtnis / Auto-Timeline / Vorschläge
- nicht als zwei Reiter trennen

### Projekte
Hier landen:

- **pds**-artige betriebliche Struktur
- **Buroo**-artige Angebots-/Nachverfolgungslogik
- Material-/Lead-/Baustellenbezug
- keine Sales-Sonderwelt

### Aufgaben
Hier landen:

- aus Mail/Messenger/Dokumenten erkannte To-dos
- private/fokussierte To-dos aus **Rise**
- ruhige Priorisierung statt extra Fokus-App

### Kalender
Hier landen:

- Follow-ups aus Mail
- Terminempfehlungen
- Fristen aus Dokumenten
- Besprechungsbezug aus Büro-/Mail-Kontext

### Visualizer
Hier landen nur Dinge, die wirklich **Zusammenhänge sichtbar machen**:

- Wissensspeicher
- Kontext verknüpfen
- Query/Recall später
- kein Agenten-Spielplatz für Endnutzer

### Einstellungen / Admin
Hierhin gehören die technischeren Themen:

- **AirLLM** / Hardwaremodus
- Modellwahl / Leistungsmodus
- evtl. spätere Telefonie-/Erreichbarkeitsoptionen
- Agenten-/Tooling-/Ops-Themen
- niemals als Alltagsreiter

## 3. Was ausdrücklich **kein eigener Hauptreiter** wird

Diese Themen bekommen **keinen neuen Hauptreiter**:

- Büroassistent
- E-Mail-Assistent
- Baustellenjournal
- Zeitgedächtnis
- Wissensspeicher
- AI Memory
- Telefonie / Routing
- lokale KI-Leistung
- Agenten-Manager
- Fokus / Privat

Alle diese Themen werden **in bestehende Reiter eingewebt**.

## 4. Praktische Integrationsform je Reiter

| Reiter | Form der Integration |
| --- | --- |
| Dashboard | kompakte Hinweis-Karten, Statusfelder, offene nächste Schritte |
| Postfach | rechte Assistenzspalte, Kontakt-Tags, Antwortvorschläge, Wichtigkeit |
| Messenger | Journalpanel, Zusammenfassung, To-do-/Berichtssektion |
| Upload | Review-Bereich, Vorschlagsbereich, Folgeaktionspanel |
| Zeiterfassung | Zusatzsektion „Zeitgedächtnis“, mobile Aktionskarten |
| Projekte | Zusatzkarten für Nachverfolgung, Angebot, Materialhinweise |
| Aufgaben | Priorisierungsbereich, erkannte Aufgaben, Fokusansicht |
| Kalender | Follow-up-/Fristenpanel |
| Visualizer | Kontext-/Wissensansicht |
| Einstellungen | Hardware-, Modell-, Leistungs- und Admin-Extras |

## 5. Priorisierte Reihenfolge für die Umsetzung

Damit es nicht zerfasert, werden die Anhänge so abgearbeitet:

1. **Postfach ausbauen**
   - Fyxer / Superhuman / BARMER
2. **Messenger ausbauen**
   - Compa / WeSpotr
3. **Upload / Dokumente ausbauen**
   - BauAI / Paperless-Prinzip
4. **Zeiterfassung ausbauen**
   - StempelKraft / Memtime
5. **Dashboard / Projekte / Aufgaben harmonisieren**
   - Buroo / pds / Rise
6. **Settings / Visualizer / Memory-Themen**
   - AirLLM / Memory / Agent-Architektur

## 6. Verbindliche Regel für Codex

> **Neue Ideen aus Anhängen werden zuerst einem bestehenden Reiter zugeordnet.**
> **Nur wenn sie dort nicht sauber unterzubringen sind, dürfen sie als Extra innerhalb dieses Reiters erscheinen.**
> **Sie werden nicht als neuer Hauptreiter gebaut.**

Diese Regel ist für weitere Produktintegration verbindlich und merge-blockend bei Verstößen.
