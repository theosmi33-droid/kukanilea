KUKANILEA Systems — Blueprint v1 (semi-technisch, zum Protokollieren)

Ziel: lokales KI-System für Betriebe, das Ordnung + Wissen + Kontrolle liefert, mit Agenten, Rollenrechten, Audit, Re-Extract Lernen – ohne die Kontrolle an “KI” abzugeben.

⸻

1) Leitprinzipien (die Regeln, die nie brechen dürfen)

P1 — DB ist die Wahrheit
	•	Datenbank (DB) ist die Single Source of Truth.
	•	Dateisystem ist “Realität” (Dateien existieren physisch), aber DB entscheidet, was es ist, wo es hingehört, wer es sehen darf.

P2 — KI ist Vorschlag, Mensch entscheidet
	•	Agenten dürfen:
	•	finden, zusammenfassen, vorschlagen, warnen
	•	Agenten dürfen nicht:
	•	endgültig verschieben/löschen/ändern ohne Bestätigung (oder Admin-Policy).

P3 — Manuelle Finder-Änderungen sind erlaubt, aber werden erkannt
	•	Wenn jemand im Finder umbenennt/verschiebt:
	•	System blockiert nichts
	•	System erkennt Drift beim nächsten Index-Lauf
	•	zeigt Änderungsvorschläge + “Bestätigen/Zurücksetzen/ignorieren”

P4 — Sicherheit “deny by default”
	•	Neue Rollen sehen erstmal nichts, bis Admin Rechte setzt.
	•	Alles ist auditierbar.

P5 — Keine Duplikate als “Wahrheit”
	•	Ein Dokument hat eine stabile Dokument-ID in der DB.
	•	Dateiversionen = Versionen dieser ID (History), keine doppelten Einträge.

⸻

2) Systemschichten (7 Layer, wer darf mit wem sprechen)
	1.	Storage Layer (Dateisystem)
	•	Ordner & Dateien
	•	Physische Moves/Renames
	2.	Data Layer (DB) — Wahrheit
	•	Kunden, Objekte, Dokumente, Metadaten, Rechte, Aktionen
	3.	Index Layer
	•	Volltext/Embedding/Metadaten-Index
	•	Dedupe & Versions
	4.	Permission Layer (RBAC)
	•	Rollen → erlaubte Ordner/Doctypes/Actions
	5.	Agent Layer
	•	spezialisierte Agenten mit Identität (Büro, Bauleitung, Archiv …)
	6.	Assistant Layer (UI/Chat)
	•	“Fragen → Treffer → Aktionen”
	•	immer Rollenfilter + Bestätigung
	7.	Audit & Control Layer
	•	Logs
	•	Notfallmodus (readonly / admin-only)
	•	Revisions-/Hash-Prüfung

Merksatz:
UI → fragt DB → DB entscheidet → Index hilft → Agent schlägt vor → User bestätigt → DB schreibt → Storage wird bewegt → Audit schreibt mit.

⸻

3) Kernobjekte (was existiert im System)

3.1 Kunde
	•	hat Kundennummer (KDNr)
	•	kann mehrere Objekte/Einheiten haben (dein Modell: neues Objekt = neue KDNr möglich)

3.2 Objekt/Einheit
	•	“Baustelle / Straße / Einheit”
	•	kann optional eine interne Objekt-ID haben (nur Admin sichtbar, um Fehler zu fixen)

3.3 Dokument
	•	stabile document_id
	•	hat:
	•	doctype (z. B. Angebot, Rechnung, Foto)
	•	tags (Bad, Küche, Aufmaß)
	•	owner (KDNr/Objekt)
	•	versions (Dateipfade über Zeit)

3.4 Version
	•	Pfad, Hash, Größe, Zeit
	•	gehört zu einer document_id
	•	macht History sichtbar (du wolltest das: “Dokumentversionen: Ja”)

⸻

4) Berechtigungen (RBAC) — wie du Kontrolle behältst

Rollen (Start)
	•	Admin
	•	Büro
	•	Bauleitung
	•	Handwerker
	•	Aushilfe
(Erweiterbar)

Rechte pro Pfad im Template-Baum

Pro Knoten (Ordner) speicherst du Häkchen:
	•	Lesen
	•	Hochladen
	•	Verschieben

Optional: Unterordner sperren (du willst optional, nicht zwingend).

“Personalisierte KI” ohne Datenkopien
	•	Jeder Account hat:
	•	eigene Präferenzen
	•	eigenes Feedback
	•	eigene Memory-Notizen
	•	Aber: Zugriff auf Dokumente bleibt RBAC-gefiltert.

⸻

5) Template-Baum (Admin editierbar)

Admin kann in der UI:
	•	Ordner hinzufügen/umbenennen
	•	Ordner verschieben (Baum)
	•	jedem Ordner erlaubte Dokumenttypen zuweisen
	•	Rechte pro Rolle setzen (lesen/hochladen/verschieben)
	•	Export/Import als JSON (Backup, Git)

Wichtig: Template-Baum ist “Policy”.
Das heißt: Review-Wizard + Assistant folgen ihm.

⸻

6) Extraktion & Lernen (ohne Würfeln)

Extraktion ist 2-stufig
	1.	Layout-Extraktion (Seite 1–3):

	•	TOP / MID / BOT getrennt
	•	Bold/Font/Mitte Scoring
	•	Liefert:
	•	Volltext
	•	Feldkandidaten + Belegzeilen

	2.	OCR nur wenn nötig:

	•	oder wenn User “Re-Extract erzwingen” klickt

Re-Extract Button
	•	probiert alternative Strategie (andere DPI, OCR erzwungen, andere Layout-Gewichte)
	•	speichert Ergebnis als “Extraktion v2”
	•	User wählt “besser” → das wird Training Log

Lernen = nur aus Korrekturen
	•	wenn User Feld korrigiert:
	•	Speichern: vorher/nachher + Beleg + doc_id + doctype
	•	später nutzt System diese Patterns (Regeln/Heuristiken) bevorzugt

⸻

7) Index (Suche) — schnell, dedupliziert, nur Kundenablage

Quelle
	•	nur Tophandwerk_Kundenablage (Eingang unsichtbar)

Dedupe/Versions
	•	Hash + Größe + “nahe gleicher Name” → wird Version, nicht neuer Treffer
	•	im Assistant:
	•	1 Trefferkarte = 1 Dokument
	•	History-Dropdown zeigt Versionen

Reindex
	•	Standard: täglich nachts
	•	Admin kann:
	•	Zeitplan ändern
	•	manuell starten
	•	Status sehen (Queue)

⸻

8) Agentenmodell (deine Vision in saubere Rollen gepackt)

Agenten (Start)
	•	Archiv-Agent
	•	erkennt Duplikate
	•	erkennt Drift (Finder-Moves)
	•	schlägt Korrektur vor
	•	Büro-Agent
	•	sucht Dokumente
	•	erstellt Zusammenfassung
	•	hilft bei Angebots-/Schreiben-Entwürfen (nur Entwurf)
	•	Bauleiter-Agent
	•	sucht Fotos/Aufmaß
	•	erstellt Baustellen-Kontext (nur Vorschläge)
	•	Supervisor-Agent (Admin-only)
	•	darf Policies ändern
	•	darf Notfallmodus setzen
	•	überwacht andere Agenten

Agenten kommunizieren
	•	ja, aber über Tasks (nicht “wild”):
	•	“Duplikat prüfen”
	•	“fehlende Daten”
	•	“Unklare Zuordnung”

⸻

9) Tasks & Benachrichtigungen (das “es gibt was zu tun” Gefühl)

Task-Typen:
	•	Unklare Zuordnung (KDNr fehlt / Objekt unklar)
	•	Drift entdeckt (Finder-Move)
	•	Duplikat vermutet
	•	OCR schwach (Confidence niedrig)
	•	Template-Konflikt (Doctype passt nicht zum Zielpfad)

Benachrichtigung:
	•	UI-Badge
	•	optional später Push/Email

⸻

10) Audit / Forensik / Notfall

Audit minimal (dein Minimum)
	•	user_name
	•	role
	•	timestamp
	•	action_type

Audit sinnvoll (empfohlen, später erweiterbar)
	•	doc_id
	•	file_path_before/after
	•	fields_changed
	•	reason (z. B. “user_confirmed”)

Notfallmodus
	•	READONLY: niemand darf verschieben
	•	ADMIN_ONLY: nur Admin sieht UI

⸻

11) Monetarisierung / B2B-Fit (Architektur-Konsequenz)

Wenn du B2B willst, brauchst du später:
	•	“Tenant” (Firma) als oberste DB-Ebene
	•	Lizenzprüfung (dein Schlüsselmodell) → online check alle 6h
	•	Export/Import (Migration)

Blueprint-Regel dazu:
Lizenz darf niemals die Daten blockieren → nur Features/Agenten/Sync einschränken, nicht Zugriff auf eigene Dateien.

⸻

12) Was wir als Nächstes implementieren (Blueprint → Code)

Implementations-Reihenfolge (schnellster Sprung)
	1.	Template-Baum in DB + Rechte (read/upload/move)
	2.	Index: nur Kundenablage + dedupe + versions
	3.	Assistant: Karten, Aktionen (Öffnen/Finder/Zusammenfassung/Kalender-Read)
	4.	Review-Flow: Doctype/Folder zuerst, dann Metadaten, dann Summary “Bearbeiten/Fertig”
	5.	Re-Extract + Training Logs

⸻

Wenn du das “zwischenspeichern” willst

Ich empfehle dir: docs/blueprint_v1.md im Repo.

cd ~/Tophandwerk
mkdir -p docs
nano docs/blueprint_v1.md


⸻

13) 10 “No-Go Regeln” (klein, aber extrem wichtig)
	1.	Kein Move ohne Audit.
	2.	Kein Agent schreibt ohne Bestätigung/Policy.
	3.	Keine Duplikate als neue Dokumente, wenn Hash gleich.
	4.	Eingang nie im Assistant sichtbar.
	5.	RBAC wird immer serverseitig geprüft (nicht nur UI).
	6.	Template-Baum ist die einzige Quelle für erlaubte Zielpfade.
	7.	Manuelle Finder-Änderungen werden nie verboten, nur erkannt.
	8.	Training nur aus Nutzer-Korrekturen.
	9.	“Admin kann alles” bleibt immer möglich (Notfall).
	10.	DB bleibt Master, Index ist nur Abbild.

⸻

Wenn du “Go” sagst, mache ich als nächstes die konkrete Umsetzung in tophandwerk_core.py (vollständig, nano-fertig) für:
	•	Template-Baum in DB + Export/Import JSON
	•	RBAC read/upload/move (serverseitig)
	•	Index: nur Kundenablage + dedupe + versions
	•	Audit-Tabelle (minimal + erweiterbar)
