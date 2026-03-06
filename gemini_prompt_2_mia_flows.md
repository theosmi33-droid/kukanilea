# Gemini Prompt 2 — Cross-Tool "MIA Flows" (End-to-End)

Kontext: Handwerksbetriebe (z. B. SHK, Elektro, Dach, Maler, Trockenbau, GaLaBau) mit durchgängigen Abläufen über CRM, ERP, Kalender, E-Mail, DMS, Zeiterfassung und Einkauf.

## 1) Angebotsanfrage per E-Mail → Angebotsprozess starten
- **Trigger (User message):** "Neue Mail von Müller GmbH mit Leistungsverzeichnis ist da — bitte Angebot vorbereiten."
- **Plan Steps:**
  1. E-Mail + Anhänge klassifizieren
  2. Kundendaten abgleichen/neu anlegen
  3. Projekt + Angebotsentwurf anlegen
  4. Kalkulationsaufgaben erzeugen
  5. Antwortmail als Draft vorbereiten
- **Tool Actions (mit Inputs):**
  - `Email.fetch(thread_id="mail_7841")`
  - `DMS.parse_attachment(file="lv_mueller_2026.pdf")`
  - `CRM.upsert_customer(name="Müller GmbH", email="info@mueller-gmbh.de")`
  - `ERP.create_quote(project_type="Sanierung", customer_id="crm_122")`
  - `Tasks.create(list="Kalkulation", title="Positionen prüfen", assignee="kalkulation@betrieb.de")`
  - `Email.create_draft(to="info@mueller-gmbh.de", template="eingang_bestaetigung_angebot")`
- **Confirm-Gates (wo nötig):**
  - Freigabe bei Neukunde mit unvollständiger Adresse
  - Freigabe vor Versand des Angebots-Drafts
- **Audit Events (welche):**
  - `email_ingested`, `attachment_parsed`, `customer_upserted`, `quote_created`, `task_created`, `draft_created`
- **Failure Modes + Recovery:**
  - PDF unlesbar → OCR-Fallback + Rückfrage an User
  - Dublette im CRM → Merge-Vorschlag mit Confirm-Gate

## 2) Telefonnotiz "Rohrbruch" → Soforteinsatz disponieren
- **Trigger:** "Kunde Weber meldet Rohrbruch, heute noch jemanden schicken."
- **Plan Steps:** Ticket anlegen → Priorisieren → Techniker suchen → Termin blocken → SMS/E-Mail bestätigen
- **Tool Actions:**
  - `CRM.search_contact(query="Weber")`
  - `ServiceDesk.create_ticket(type="Notfall", sla="4h")`
  - `Dispatch.find_nearest_skill(skill="Sanitär", area="PLZ 50667")`
  - `Calendar.book(slot="2026-03-07T14:00", technician="tech_04")`
  - `Messaging.send(channel="sms", to="+4917...", template="notfall_eta")`
- **Confirm-Gates:** Manuelle Freigabe, falls Überstundenzuschlag > 25%
- **Audit Events:** `ticket_created`, `priority_set`, `technician_assigned`, `appointment_booked`, `customer_notified`
- **Failure + Recovery:** Kein freier Techniker → Eskalation an Subunternehmer-Pool + Kunde bekommt alternatives Zeitfenster

## 3) Baustellenprotokoll per Spracheingabe → Doku + Aufgaben
- **Trigger:** "Hier ist mein Baustellenbericht von heute, bitte sauber ins Projekt übernehmen."
- **Plan Steps:** Transkribieren → Projekt zuordnen → Mängel extrahieren → Aufgaben + Fristen anlegen
- **Tool Actions:**
  - `Voice.transcribe(audio_id="aud_553")`
  - `Projects.match(context="Baustelle Schule Nord")`
  - `NLP.extract_issues(text="...")`
  - `Tasks.bulk_create(project_id="prj_88", items=[...])`
  - `DMS.store(file="baustellenbericht_2026-03-06.txt", folder="Protokolle")`
- **Confirm-Gates:** Bestätigung vor Mangelklassifikation "kritisch"
- **Audit Events:** `voice_transcribed`, `project_matched`, `issues_extracted`, `tasks_created`, `report_archived`
- **Failure + Recovery:** Falsche Projektzuordnung → Top-3 Matching-Vorschläge anzeigen

## 4) Material unter Mindestbestand → Einkauf auslösen
- **Trigger:** "Kupferrohr 18mm ist unter Minimum, bitte nachbestellen."
- **Plan Steps:** Bestand prüfen → Lieferant wählen → Bestellung erzeugen → Freigabe → Versand der PO
- **Tool Actions:**
  - `Inventory.get_stock(sku="CU-18")`
  - `Procurement.get_preferred_supplier(sku="CU-18")`
  - `ERP.create_purchase_order(lines=[{"sku":"CU-18","qty":120}])`
  - `Approvals.request(type="PO", amount=1840.00)`
  - `Email.send(to="orders@lieferant.de", attachment="PO-4412.pdf")`
- **Confirm-Gates:** CFO-Freigabe bei Bestellungen > 1.500 €
- **Audit Events:** `stock_checked`, `supplier_selected`, `po_created`, `approval_requested`, `po_sent`
- **Failure + Recovery:** Lieferant nicht lieferfähig → sekundären Lieferanten automatisch anfragen

## 5) Auftragszusage vom Kunden → Projektstart-Workflow
- **Trigger:** "Kunde hat Angebot A-204 bestätigt, bitte alles starten."
- **Plan Steps:** Angebot in Auftrag wandeln → Projektplan erzeugen → Kickoff-Termin → Team informieren
- **Tool Actions:**
  - `ERP.convert_quote_to_order(quote_no="A-204")`
  - `Projects.create_from_template(template="Badsanierung_standard")`
  - `Calendar.propose_slots(participants=["bauleitung","kunde"])`
  - `Chat.post(channel="#einsaetze", message="Neues Projekt PRJ-204 gestartet")`
- **Confirm-Gates:** User-Freigabe für finalen Projektstart bei offener Anzahlung
- **Audit Events:** `quote_converted`, `project_created`, `kickoff_suggested`, `team_notified`
- **Failure + Recovery:** Fehlende Anzahlungsbuchung → Finanz-Task erzeugen, Startstatus "on hold"

## 6) Eingangsrechnung per PDF → Prüfung + Verbuchung
- **Trigger:** "Neue Rechnung von Elektrohandel im Posteingang — bitte prüfen und verbuchen."
- **Plan Steps:** OCR + Datenextraktion → PO-Match → Freigabekette → Buchung
- **Tool Actions:**
  - `DMS.parse_invoice(file="RE-9981.pdf")`
  - `ERP.match_invoice_to_po(invoice_no="9981")`
  - `Approvals.route(role_chain=["Bauleiter","Buchhaltung"])`
  - `Accounting.post_invoice(cost_center="Montage")`
- **Confirm-Gates:** Abweichung > 5% zwischen PO und Rechnung
- **Audit Events:** `invoice_parsed`, `po_matched`, `approval_routed`, `invoice_posted`
- **Failure + Recovery:** Kein PO gefunden → Ausnahmeworkflow "ungeplante Beschaffung"

## 7) Wetterwarnung am Einsatzort → Termin umplanen
- **Trigger:** "Für morgen Sturmwarnung auf Baustelle Köln, was verschieben wir?"
- **Plan Steps:** Wetterrisiko prüfen → betroffene Außentermine identifizieren → neue Slots vorschlagen → Kunden informieren
- **Tool Actions:**
  - `Weather.get_alerts(region="Köln")`
  - `Calendar.list_jobs(date="2026-03-07", type="Outdoor")`
  - `Dispatch.replan(jobs=[...], constraints="skill+travel")`
  - `Email.bulk_draft(template="wetterbedingte_verschiebung")`
- **Confirm-Gates:** Freigabe der finalen Kundenkommunikation
- **Audit Events:** `weather_alert_received`, `jobs_flagged`, `replan_generated`, `drafts_created`
- **Failure + Recovery:** Keine Alternativslots → Warteliste + priorisierte Nachholtermine

## 8) Kunde fragt Status per WhatsApp → Live-Statusantwort
- **Trigger:** "Wann kommt euer Monteur?"
- **Plan Steps:** Kontakt identifizieren → Ticket/Termin laden → ETA berechnen → Antwort senden
- **Tool Actions:**
  - `Messaging.identify_contact(channel="whatsapp", handle="+49...")`
  - `ServiceDesk.get_open_job(contact_id="crm_66")`
  - `GPS.estimate_eta(technician="tech_09", destination="job_771")`
  - `Messaging.send(channel="whatsapp", template="eta_live", vars={"eta":"16:20"})`
- **Confirm-Gates:** Kein Gate bei Standard-Statusauskunft
- **Audit Events:** `contact_resolved`, `job_retrieved`, `eta_computed`, `status_sent`
- **Failure + Recovery:** GPS nicht verfügbar → statische ETA aus Kalender + Transparenzhinweis

## 9) Überfällige Angebote → Follow-up Kampagne
- **Trigger:** "Zeig mir alle Angebote älter als 14 Tage und bereite Nachfass-Mails vor."
- **Plan Steps:** Angebote filtern → priorisieren → personalisierte Drafts erstellen → Reminder-Tasks
- **Tool Actions:**
  - `ERP.list_quotes(status="open", older_than_days=14)`
  - `CRM.score_leads(model="close_probability")`
  - `Email.bulk_create_drafts(template="followup_angebot_v2")`
  - `Tasks.bulk_create(list="Vertrieb", title="Nachtelefonieren Angebot")`
- **Confirm-Gates:** Sammelfreigabe vor Serienversand
- **Audit Events:** `quotes_filtered`, `leads_scored`, `drafts_prepared`, `tasks_created`
- **Failure + Recovery:** Fehlende Ansprechpartnerdaten → CRM-Data-Cleanup-Task

## 10) Monteur stempelt aus → Tagesbericht + Zeiten buchen
- **Trigger:** "Ich bin fertig für heute, bitte Zeiten auf Projekte buchen."
- **Plan Steps:** Zeitbuchungen aggregieren → Projekten zuordnen → Bericht erzeugen → Freigabe an Vorarbeiter
- **Tool Actions:**
  - `TimeTracking.stop_shift(user="monteur_03")`
  - `TimeTracking.allocate(entries="today", strategy="job_code")`
  - `Reporting.generate_daily(user="monteur_03")`
  - `Approvals.request(type="timesheet", approver="vorarbeiter_01")`
- **Confirm-Gates:** Freigabe bei >10h Arbeitszeit
- **Audit Events:** `shift_stopped`, `time_allocated`, `report_generated`, `timesheet_submitted`
- **Failure + Recovery:** Unklare Zuordnung → interaktive Aufteilung pro Einsatz

## 11) Mangelmeldung vom Kundenportal → Gewährleistungsprozess
- **Trigger:** "Im Portal wurde ein Mangel an Auftrag 2025-332 gemeldet."
- **Plan Steps:** Gewährleistungsstatus prüfen → Ticket erstellen → Vor-Ort-Termin → Dokumentation
- **Tool Actions:**
  - `Portal.fetch_case(case_id="GP-22")`
  - `ERP.check_warranty(order_id="2025-332")`
  - `ServiceDesk.create_ticket(type="Gewährleistung")`
  - `Calendar.schedule_visit(window="next_48h")`
  - `Email.send(template="warranty_received")`
- **Confirm-Gates:** Freigabe nötig, falls außerhalb Gewährleistungsfrist (Kulanzentscheidung)
- **Audit Events:** `case_received`, `warranty_checked`, `ticket_created`, `visit_scheduled`, `customer_ack_sent`
- **Failure + Recovery:** Frist unklar → Vertragsdokument automatisch aus DMS laden

## 12) Neue Baustelle gewonnen → Sicherheitsunterweisung planen
- **Trigger:** "Neues Großprojekt startet Montag, alle Teams müssen Unterweisung erhalten."
- **Plan Steps:** Teamliste ziehen → Pflichtschulungen prüfen → Termine blocken → Nachweise einsammeln
- **Tool Actions:**
  - `HR.get_assigned_workers(project_id="prj_990")`
  - `Compliance.check_training_status(workers=[...], training="SiGe")`
  - `Calendar.book_group_session(duration="90m")`
  - `DMS.create_checklist(name="Unterweisungsnachweise")`
- **Confirm-Gates:** Freigabe bei Teammitgliedern ohne gültige Unterweisung
- **Audit Events:** `workers_loaded`, `compliance_checked`, `training_scheduled`, `checklist_created`
- **Failure + Recovery:** Keine gemeinsame Zeit → zwei Ersatztermine automatisch erzeugen

## 13) Offene Posten überfällig → Mahnlauf
- **Trigger:** "Starte Mahnlauf für alle Rechnungen über 30 Tage."
- **Plan Steps:** Debitorenliste → Mahnstufe berechnen → Schreiben erstellen → Versandkanal wählen
- **Tool Actions:**
  - `Accounting.list_overdue(days=30)`
  - `Accounting.compute_dunning_level(customer_id="...")`
  - `DMS.generate_letters(template="mahnung_stufe")`
  - `Email.bulk_send_or_print(rule="per_customer_preference")`
- **Confirm-Gates:** Freigabe durch Buchhaltung vor finalem Versand
- **Audit Events:** `overdue_loaded`, `dunning_level_set`, `letters_generated`, `dunning_sent`
- **Failure + Recovery:** Disput-Flag vorhanden → Fall in Klärungs-Queue statt Mahnung

## 14) Subunternehmer benötigt Einsatzinfos → Freigabeprozess
- **Trigger:** "Schick dem Subunternehmer alle Unterlagen für Einsatz Freitag."
- **Plan Steps:** Relevante Doku sammeln → DSGVO-Check → Freigabe → Versand mit Ablaufdatum
- **Tool Actions:**
  - `DMS.collect(project_id="prj_410", tags=["Plan","LV","Sicherheitsblatt"])`
  - `Security.scan_documents(policy="external_share")`
  - `Approvals.request(type="external_data_share")`
  - `Share.create_secure_link(expiry_days=7, recipient="sub@firma.de")`
- **Confirm-Gates:** Pflichtfreigabe für externe Datenweitergabe
- **Audit Events:** `docs_collected`, `security_scan_done`, `share_approved`, `secure_link_sent`
- **Failure + Recovery:** Policy-Verstoß → sensible Seiten automatisch schwärzen + erneut prüfen

## 15) Kunde wünscht Terminänderung → Dispo und Ressourcen neu planen
- **Trigger:** "Kunde Schmidt will den Termin nächste Woche statt morgen."
- **Plan Steps:** Bestehenden Termin finden → Ressourcen freigeben → neuen Slot planen → Bestätigung senden
- **Tool Actions:**
  - `Calendar.find(appointment_id="apt_442")`
  - `Dispatch.release_resources(appointment_id="apt_442")`
  - `Calendar.reschedule(preferences="KW11")`
  - `Email.send(template="terminbestaetigung_neu")`
- **Confirm-Gates:** Freigabe, wenn Vertragsstrafe bei Verschiebung möglich
- **Audit Events:** `appointment_found`, `resources_released`, `appointment_rescheduled`, `confirmation_sent`
- **Failure + Recovery:** Kein passender Slot → Wartelistenlogik + Rückrufaufgabe

## 16) Neue Online-Bewertung negativ → Service-Recovery
- **Trigger:** "Wir haben eine 2-Sterne-Bewertung bekommen, bitte sofort reagieren."
- **Plan Steps:** Bewertung analysieren → Kundenfall matchen → interne Eskalation → Antwortentwurf
- **Tool Actions:**
  - `Reputation.fetch_latest(platform="Google")`
  - `NLP.sentiment_and_topic(review_id="rev_09")`
  - `CRM.match_case(by="name+date+address")`
  - `Tasks.create(priority="high", title="Rückruf unzufriedener Kunde")`
  - `Email.create_draft(template="review_recovery")`
- **Confirm-Gates:** Kommunikationsfreigabe durch Serviceleitung
- **Audit Events:** `review_ingested`, `topic_classified`, `case_matched`, `escalation_task_created`, `draft_created`
- **Failure + Recovery:** Kein eindeutiger Match → öffentliche neutrale Antwort + Bitte um Kontaktdaten

## 17) Projektfortschritt Freitag 16:00 → Wochenreport an Bauherrn
- **Trigger:** "Erstelle und sende den Wochenstatus für Projekt Kita-West."
- **Plan Steps:** KPIs sammeln → Fotos/Meilensteine einbinden → Report generieren → Mail-Draft
- **Tool Actions:**
  - `Projects.get_kpis(project_id="kita_west")`
  - `DMS.fetch_latest_photos(project_id="kita_west")`
  - `Reporting.render(template="wochenreport_bauherr")`
  - `Email.create_draft(to="bauherr@...", subject="Wochenstatus KW10")`
- **Confirm-Gates:** Bauleiter-Freigabe vor Versand
- **Audit Events:** `kpis_loaded`, `media_attached`, `report_rendered`, `draft_prepared`
- **Failure + Recovery:** Fehlende Fotodoku → automatische Erinnerung an Vor-Ort-Team

## 18) Neue Mitarbeiterin startet → Onboarding-Flow
- **Trigger:** "Anna startet am 1.4., richte alles ein."
- **Plan Steps:** HR-Stammdaten → Accounts → Schulungen → Begrüßungsplan
- **Tool Actions:**
  - `HR.create_employee(name="Anna Keller", role="Projektassistenz")`
  - `IAM.provision_accounts(systems=["Mail","CRM","Zeiterfassung"])`
  - `LMS.assign_courses(track="Onboarding_Büro")`
  - `Calendar.create_plan(events=["Willkommen","Tool-Schulung"])`
- **Confirm-Gates:** IT-Freigabe bei erweiterten Rechten
- **Audit Events:** `employee_created`, `accounts_provisioned`, `courses_assigned`, `onboarding_plan_created`
- **Failure + Recovery:** Account-Provisioning schlägt fehl → IT-Ticket mit Retry alle 30 min

## 19) Verbrauchsmaterial pro Baustelle zu hoch → Kostenalarm
- **Trigger:** "Warum sind die Materialkosten bei Projekt Nord 18% über Soll?"
- **Plan Steps:** Ist/Soll analysieren → Treiber identifizieren → Maßnahmenaufgaben erstellen
- **Tool Actions:**
  - `Controlling.compare_budget(project_id="nord", dimension="material")`
  - `ERP.drilldown_costs(group_by="sku,week")`
  - `Analytics.detect_anomalies(model="cost_spike")`
  - `Tasks.bulk_create(list="Controlling", items=[...])`
- **Confirm-Gates:** Keine, rein analytischer Modus
- **Audit Events:** `budget_compared`, `cost_drilldown_done`, `anomalies_detected`, `action_tasks_created`
- **Failure + Recovery:** Fehlende Buchungen → Buchhaltungsabgleich starten, Analyse markieren als vorläufig

## 20) Wartungsvertrag fällig in 30 Tagen → Proaktive Terminierung
- **Trigger:** "Plane alle Wartungen, die nächsten Monat fällig sind."
- **Plan Steps:** Fällige Verträge ziehen → Cluster nach Region → Terminfenster erstellen → Kundenkontakt
- **Tool Actions:**
  - `Contracts.list_due(within_days=30, type="Wartung")`
  - `Dispatch.cluster_jobs(by="region")`
  - `Calendar.generate_slots(window="next_month")`
  - `Email.bulk_create_drafts(template="wartungstermin_vorschlag")`
- **Confirm-Gates:** Sammelfreigabe für Massenversand
- **Audit Events:** `contracts_loaded`, `jobs_clustered`, `slots_generated`, `drafts_ready`
- **Failure + Recovery:** Unvollständige Kontaktdaten → Omni-Channel Fallback (SMS + Anrufliste)

## 21) Unfallmeldung auf Baustelle → Incident-Workflow
- **Trigger:** "Es gab einen Arbeitsunfall, starte den Meldeprozess."
- **Plan Steps:** Incident erfassen → Sicherheitsbeauftragte informieren → Behördliche Fristen tracken → Dokumentation sichern
- **Tool Actions:**
  - `Safety.create_incident(severity="high", location="Baustelle Ost")`
  - `Alert.notify(role="Sicherheitsbeauftragter", channel="phone+mail")`
  - `Compliance.create_deadline_tasks(regulation="BG")`
  - `DMS.lock_evidence_folder(case_id="inc_77")`
- **Confirm-Gates:** Pflichtbestätigung vor externen Meldungen
- **Audit Events:** `incident_created`, `stakeholders_alerted`, `compliance_tasks_created`, `evidence_locked`
- **Failure + Recovery:** Fehlende Pflichtfelder → Formular-Validation mit guided completion

## 22) Kunde sendet Planänderung → Change-Order Prozess
- **Trigger:** "Der Kunde möchte statt Standardfliesen jetzt Premiumfliesen."
- **Plan Steps:** Änderungswunsch erfassen → Mehrkosten kalkulieren → Nachtrag erstellen → Freigabe einholen
- **Tool Actions:**
  - `CRM.log_change_request(order_id="AU-772", change="Premiumfliesen")`
  - `ERP.recalculate_quote(delta_items=[...])`
  - `ERP.create_change_order(reference="AU-772")`
  - `Email.create_draft(template="nachtrag_freigabe")`
- **Confirm-Gates:** Kundenfreigabe des Nachtrags zwingend
- **Audit Events:** `change_logged`, `costs_recalculated`, `change_order_created`, `approval_request_sent`
- **Failure + Recovery:** Preislisten fehlen → Einkaufspreise live abfragen, sonst Nachtrag als "vorläufig"

## 23) Krankmeldung Techniker → Einsatzkette stabilisieren
- **Trigger:** "Max ist morgen krank, plane alle Einsätze um."
- **Plan Steps:** Betroffene Termine identifizieren → Ersatz finden → Kunden neu informieren
- **Tool Actions:**
  - `HR.mark_absence(user="max", date="2026-03-07")`
  - `Dispatch.list_assignments(user="max", date="2026-03-07")`
  - `Dispatch.reassign(jobs=[...], strategy="skill_first")`
  - `Messaging.bulk_send(template="terminupdate_krankheitsbedingt")`
- **Confirm-Gates:** Freigabe bei Einsatz von externen Kräften
- **Audit Events:** `absence_recorded`, `assignments_loaded`, `jobs_reassigned`, `customers_notified`
- **Failure + Recovery:** Keine Ersatzkraft → Priorisierung nach SLA + Teilverschiebung

## 24) Behördentermin angekündigt → Compliance-Dokumente bündeln
- **Trigger:** "Morgen kommt die Aufsichtsbehörde, stell alle Nachweise zusammen."
- **Plan Steps:** Dokumentencheckliste laden → Nachweise sammeln → Lücken markieren → Exportmappe erzeugen
- **Tool Actions:**
  - `Compliance.load_checklist(type="Baustellenprüfung")`
  - `DMS.collect(tags=["Gefährdungsbeurteilung","Unterweisung","Prüfprotokoll"])`
  - `QA.validate_completeness(bundle_id="cmp_11")`
  - `DMS.export_zip(name="Behoerdenmappe_2026-03-07")`
- **Confirm-Gates:** Keine, read-only Sammelprozess
- **Audit Events:** `checklist_loaded`, `documents_collected`, `completeness_checked`, `bundle_exported`
- **Failure + Recovery:** Fehlende Dokumente → Auto-Task an Dokumentenverantwortliche mit Deadline

## 25) Monatsende → Management-Cockpit aktualisieren
- **Trigger:** "Aktualisiere das Monats-Cockpit mit Umsatz, Marge, Auslastung und offenen Risiken."
- **Plan Steps:** KPI-Daten einsammeln → konsolidieren → Abweichungen markieren → Dashboard publizieren
- **Tool Actions:**
  - `BI.fetch_kpis(period="2026-02", metrics=["Umsatz","Marge","Auslastung"])`
  - `Risk.register_open_items(source="ServiceDesk+Controlling")`
  - `Analytics.compute_variances(vs="Plan")`
  - `BI.publish_dashboard(name="Monatscockpit")`
  - `Email.send(to="leitung@betrieb.de", template="cockpit_ready")`
- **Confirm-Gates:** CEO-Freigabe vor externer Weitergabe
- **Audit Events:** `kpis_fetched`, `risks_loaded`, `variances_computed`, `dashboard_published`, `stakeholders_informed`
- **Failure + Recovery:** Datenquellen inkonsistent → automatischer Data-Quality-Report + Recompute

