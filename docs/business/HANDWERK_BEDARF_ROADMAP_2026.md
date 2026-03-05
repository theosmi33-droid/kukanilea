# KUKANILEA Handwerk-Bedarfsbild 2026
## Von "Feature-Tool" zu "digitalem Betriebsleiter" (OpenClaw + PicoClaw)

> Arbeitsgrundlage für Produkt, Engineering und Go-to-Market.
> Ziel: messbar weniger Verwaltungsaufwand und Medienbrüche im Handwerksbetrieb.

## 1) Strategische Diagnose

Die Marktindikatoren für das deutsche Handwerk zeigen ein wiederkehrendes Muster:
- Digitalisierung wird grundsätzlich bejaht, aber im Tagesgeschäft dominieren hybride Workflows.
- Der größte operative Schmerzpunkt ist nicht fehlende Software, sondern fehlende Durchgängigkeit.
- Vertrauen (Datensicherheit, Souveränität, Kostenkontrolle) ist kaufentscheidend.

### Typische Reibungsverluste im Betrieb
- Mehrfache Datenerfassung über Angebot, Kalender, Baustellendoku und Rechnung.
- Hohe Fehleranfälligkeit durch manuelle Übergaben.
- Zeitverlust durch Suche nach Dokumenten/Fotos/Projektständen.
- Chef-Rolle bleibt Flaschenhals (Facharbeit + Disposition + Verwaltung + Kommunikation).

## 2) Produktthese für KUKANILEA

KUKANILEA wird als **Local-First Enterprise OS für Handwerksbetriebe** positioniert:
- **OpenClaw** = semantische Orchestrierung und Wissensschicht (Verstehen, Verknüpfen, Finden).
- **PicoClaw** = schlanke Ausführungseinheit für konkrete, schnelle Aktionen (Assistenz im Alltag).

### Kernversprechen
1. **Weniger Verwaltungszeit pro Woche** (administrative Entlastung).
2. **Weniger Fehler durch durchgängige Datenflüsse** (einmal erfassen, mehrfach nutzen).
3. **Volle Datensouveränität ohne Cloud-Abhängigkeit** (Vertrauen als Wettbewerbsvorteil).

## 3) Zielarchitektur entlang der 3 Säulen

## Säule A: Gedächtnis des Betriebs
Vom Dateiablage-Problem zur kontextfähigen Wissensbasis.

**Umsetzung:**
- Lokale Dokumenten-Ingestion (PDF, Office, E-Mail, Bilder, Sprachmemos).
- Automatische Indexierung, OCR, Entitäten- und Projekterkennung.
- RAG-Abfragen in Alltagssprache (Kunde, Auftrag, Zeitraum, Materialfall).

**Technische Leitlinie:**
- Local-First Retrieval mit vektor- und textbasierter Suche.
- Nachvollziehbare Quellenrückgabe in jeder KI-Antwort.

## Säule B: Automatisierter Workflow ohne Medienbruch
Vom "ich trage es überall ein" zur orchestrierten Prozesskette.

**Umsetzung:**
- Ereignisbasierte Workflows über Angebots-, Auftrags-, Termin- und Rechnungsstatus.
- Eingangs-Klassifikation (Mail/Anhang/Belegtyp) mit Handlungsvorschlag.
- Regelbaukasten für Betriebe (z. B. "Wenn Rechnung bezahlt, dann archivieren + Rückmeldung").

**Technische Leitlinie:**
- Kleine, klare Actions statt monolithischer KI-Entscheidungen.
- Human-in-the-Loop bleibt Standard (Vorschlag -> Bestätigung -> Ausführung).

## Säule C: Entlastung der Fachkräfte
Vom Tool-Lernen zur sofort nutzbaren Assistenz.

**Umsetzung:**
- Mobile Baustellen-Dokumentation per Sprache, Foto, Kurznotiz.
- Kontextsensitive Vorschläge für Material, Prüftermine, Folgeaufgaben.
- Rollenorientierte Oberflächen (Chef, Büro, Monteur).

**UX-Prinzip:**
- Werkzeugkisten-Logik statt ERP-Komplexität.
- Große, klare Aktionen; kurze Wege; robuste Offline-Nutzung.

## 4) Produkt-Roadmap für die "11 Tools"

## Gruppe A: Wissensmanagement
1. Smartes Dokumentenregister (Indexierung + semantische Suche)
2. Visuelles Lexikon (Baustellenfotos, Materialfälle, Schadenmuster)
3. Fakturierungs-Gedächtnis (Angebot/Rechnung/Material-Realität)

## Gruppe B: Prozessautomatisierung
4. KI-Poststelle (lokale Mail-/Anhang-Klassifikation)
5. Workflow-Motor (visuelle Regeln für Standardabläufe)
6. Termin-Koordinator (Zeitslots, Fahrtzeit, Materialverfügbarkeit)

## Gruppe C: Vor-Ort-Unterstützung
7. Baustellen-Doku-Helfer (Sprache -> strukturierter Bericht)
8. Material- & Lager-Copilot (Verbrauchsprognosen, Engpasswarnungen)
9. Prüf- & Wartungsassistent (Fristen, Protokolle, Nachweise)

## Gruppe D: Betriebssteuerung
10. Betriebs-Cockpit (Auslastung, Angebotsquote, Liquidität, Verbrauch)
11. Risiko-Monitor (Verzug/Kostenabweichung mit Frühwarnung)

## 5) Implementierungspriorität (90-Tage-Plan)

### Phase 1: Fundament (Tag 1-30)
- Gemeinsames Datenmodell für Auftrag, Dokument, Termin, Material.
- Lokale RAG-Basis mit nachvollziehbarer Quellenanzeige.
- Erste PicoClaw-Actions: `termin_erstellen`, `beleg_klassifizieren`, `projekt_zuordnen`.

### Phase 2: Automatisierung (Tag 31-60)
- Ereignis-/Workflow-Layer für Angebot -> Auftrag -> Rechnung.
- KI-Poststelle mit Vorschlagsmodus (kein Auto-Dispatch ohne Bestätigung).
- Mobile Doku-Flow für Foto + Sprache + Projektzuordnung.

### Phase 3: Steuerung (Tag 61-90)
- Cockpit-Metriken und Frühwarnlogik.
- Materialprognose im Vorschlagsmodus.
- Betriebsnahes Pilotpaket mit messbarer Zeiteinsparung.

## 6) KPI-Set für Produkt- und Business-Entscheidungen

Pflichtmetriken pro Pilotbetrieb:
- Verwaltungszeit pro Woche (Baseline vs. nach 30/60/90 Tagen)
- Anzahl manueller Doppelerfassungen pro Auftrag
- Durchlaufzeit Anfrage -> Angebot -> Auftrag
- Fehlerrate in Dokumentation/Faktura
- Nutzungsquote der KI-Vorschläge (angenommen/abgelehnt)

Erfolgskriterium:
- Nachweisbare Entlastung statt Feature-Menge.

## 7) Positionierung im Vertrieb

KUKANILEA wird nicht als "noch eine Software" verkauft, sondern als:
- **Digitaler Lehrling** (arbeitet zu, statt Arbeit zu erzeugen)
- **Betriebsgedächtnis** (findet Wissen sofort wieder)
- **Lokale Sicherheitszone** (keine Cloud-Abhängigkeit, volle Kontrolle)

## 8) Nicht verhandelbare Leitplanken

- Sovereign-11 einhalten (White-Mode only, Zero-CDN, lokale Assets).
- Domain-Isolation respektieren; Shared-Core nur minimal und begründet.
- KI bleibt Assistenzsystem: Vorschlag vor Ausführung, nachvollziehbar und überprüfbar.

---

**Entscheidungsregel für das Team:**
Jede neue Funktion muss eine der drei Fragen positiv beantworten:
1. Spart sie im Alltag messbar Zeit?
2. Reduziert sie Medienbrüche oder Fehler?
3. Stärkt sie Datensouveränität und Vertrauen?

Wenn nicht, kommt sie nicht in den nächsten Release-Zyklus.
