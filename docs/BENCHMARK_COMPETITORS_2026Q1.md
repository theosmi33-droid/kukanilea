# BENCHMARK_COMPETITORS_2026Q1

## Executive Summary
Wiederkehrende Muster über die analysierten Anbieter:
- `Time-to-value` wird aggressiv vermarktet: schneller Start, vorkonfigurierte Flows, geringe Einrichtungsfriktion.
- `Field + Office` ist der Kern: mobile/offline Erfassung vor Ort, strukturierte Weiterverarbeitung im Backoffice.
- `Auditierbarkeit` wird als Produktnutzen verkauft: Freigaben, Historie, Reports, nachvollziehbare Zustände.
- `AI als Automatisierung`, nicht als Selbstzweck: Triage, Routing, Zusammenfassungen, Vorschläge.
- `Compliance` ist Vertriebsargument: DSGVO-/Hosting-/Sicherheitsaussagen und klare Rollen-/Berechtigungskonzepte.

## Competitor Matrix
| Product | Target segment | Core promise | UX pattern | Key capabilities | Evidence links | Navigation path | Notes |
|---|---|---|---|---|---|---|---|
| Moltbot / ClawdBot pattern | Teams mit agentischer Workflow-Orchestrierung | Always-on Agent mit Datei-basiertem Kontext | Context-as-files (`SOUL.md`, `USER.md`, `MEMORY.md`) + proaktive Tasks | Messaging/Voice/Text Inputs, LLM/API-Layer, proaktive Kalender/Mail-Assistenz | [LinkedIn post](https://www.linkedin.com/posts/data-science-dojo_moltbot-the-next-step-in-digital-workflows-activity-7295534020375416832-7xqv), [Architecture docs](https://molt-bot.live/architecture/), [Configuration](https://molt-bot.live/configuration/) | LinkedIn Post -> Diagramm; molt-bot.live -> Architecture/Configuration | Vendor claim + third-party pattern source |
| Lovable | Produktteams mit Browser-basiertem QA-Testen | Agent testet UI wie ein Nutzer in Remote-Browsern | Testen über echte Browserinteraktion inkl. Artefakte | Klicken/Formulare, Screenshots, Console/Network, verschiedene Viewports | [Browser testing](https://docs.lovable.dev/features/browser-testing), [Testing overview](https://docs.lovable.dev/features/testing) | Docs -> Features -> Browser testing | Documented |
| Craftboxx | Handwerk (Baustelle + Büro) | Baustellenprozesse digitalisieren inkl. Doku und Integration | Mobile-first Capture, später Büroverarbeitung | Offline-Dokumentation, Fotos/Notizen, Integrationen Lexware/sevdesk | [Craftboxx](https://www.craftboxx.de/), [Dokumentation](https://www.craftboxx.de/dokumentation), [Support offline](https://support.craftboxx.de/wissensbasis/baudokumentationen-und-fotos-in-der-craftboxx-app) | Homepage -> Integrationen; Funktionen -> Dokumentation; Support -> Wissensbasis | Vendor claim + documented support behavior |
| Fonio.ai | SMB/Teams mit Telefon-Automation | AI-Telefonassistenz mit Paket-/Minutenmodell | Voice als Eingangskanal mit standardisiertem Routing | Pricing-Tiers, Datenschutz-/AVV-Doku, Hosting-Informationen | [Preise](https://www.fonio.ai/preise), [Datenschutz](https://docs.fonio.ai/Datenschutz/Datenschutz), [AVV](https://docs.fonio.ai/Datenschutz/AVV) | Website -> Preise; Docs -> Datenschutz/AVV | Vendor claim + documented legal pages |
| Placetel AI | Unternehmen mit Telefonie/Terminbedarf | Voicebot für Call-Handling und Terminierung | Voicebot-Flow mit Termin-Connector | Anrufannahme/Routing/Automatisierung, cal.com Termin-Flow | [Placetel AI](https://www.placetel.de/placetel-ai), [cal.com tutorial](https://www.youtube.com/watch?v=7Qyg377LaV8) | Website -> Placetel AI; YouTube -> Tutorial | Vendor claim |
| Starbuero | Unternehmen mit Fokus Erreichbarkeit | Externer Telefonservice statt verpasster Anfragen | Human-in-the-loop Service mit klaren Paketen | Telefonannahme/Sekretariatsservice | [Starbuero](https://www.starbuero.de/) | Website -> Leistungen/Telefonservice | Vendor claim |
| awork | Projekt-/Ressourcen-Teams | Planung + KI-Assists mit Compliance-Positionierung | Work management + KI-Hilfe in bestehenden Flows | DSGVO/Hosting-Kommunikation, KI-Policy/Anbieterinfo | [awork](https://www.awork.com/de), [awork und KI](https://support.awork.com/de/articles/12802079-awork-und-ki) | Website -> Trust/Compliance; Helpcenter -> KI | Vendor claim + documented policy text |
| Haufe Gefährdungsbeurteilung | Compliance-/Sicherheitsverantwortliche | Digitaler, rechtssicherer Prozess mit Freigaben | Geführte Freigabe- und Dashboard-Flows | Freigaben, Versionierung, Archivierung, Überfälligkeits-Dashboard | [Haufe Produktseite](https://shop.haufe.de/gefaehrdungsbeurteilung) | Shop -> Produkt -> Prozess/Funktionen | Vendor claim |
| clockin | Handwerk/Field Service | Schneller Start in digitale Zeit-/Auftragserfassung | Mobile + Browser + Integrationen als Standard | Zeiterfassung, Integrationen (DATEV/Lexware/sevdesk), Browserzugang | [clockin Zeiterfassungssoftware](https://www.clockin.de/zeiterfassungssoftware), [clockin Homepage](https://www.clockin.de/), [Support Browser](https://support.clockin.de/kann-ich-clockin-auch-%C3%BCber-den-browser-auf-dem-handy-nutzen) | Website -> Zeiterfassung/Integrationen; Support -> Browserartikel | Vendor claim + documented support behavior |
| Personio Workflow Automation | HR/People Ops | No-code Workflow-Automatisierung für HR-Prozesse | Vorlagen zuerst, Builder danach, Monitoring im Betrieb | Workflow-Vorlagen, Builder, Genehmigungen, Benachrichtigungen | [Personio workflow automation](https://www.personio.de/workflow-automation/) | Website -> Workflow Automation | Vendor claim |

## KUKANILEA Implications (No-Code Backlog Candidates)
1. Global Search + Command Palette mit RBAC-kontextabhängiger Trefferliste.
- Acceptance criteria: Suche liefert nur berechtigte Objekte; Cmd/Ctrl+K öffnet Palette; Create-from-search für Kernobjekte.
2. Field-Capture Workflow mit Offline-Queue (Foto/Notiz/Status), später deterministischer Sync.
- Acceptance criteria: Offline-Events gehen nicht verloren; Konflikte sind sichtbar und auflösbar; Sync protokolliert Request-ID.
3. Freigabe-/Audit-Flow für kritische Workflows inkl. Überfälligkeiten-Dashboard.
- Acceptance criteria: Zustandswechsel sind historisiert; Überfällige Items sichtbar; Exporte enthalten Historie.
4. Telefon-/Inbox-Intake als strukturierter Eingang statt unstrukturierter Nachrichten.
- Acceptance criteria: Intake wird klassifiziert/geroutet; Folgeaktion erzeugt Task/Lead; Fehlerfälle blockieren UI nicht.
5. Integrationsoberflächen für DATEV/Lexware/sevdesk als klar abgegrenzte Export-/Sync-Module.
- Acceptance criteria: Exportformate versioniert; Fehlermeldungen mit Korrekturhinweis; Testdatensätze reproduzierbar.

## Notes on Evidence Quality
- Aussagen mit direktem Funktions-/Doku-Beleg sind als `Documented` markiert.
- Marketing-/Wirkungsversprechen sind als `Vendor claim` markiert und vor Product-Entscheidungen gesondert zu validieren.
