# KUKANILEA Systemhandbuch

Willkommen beim offiziellen Systemhandbuch von KUKANILEA. Dieses Dokument dient als zentrale Wissensquelle für die Architektur, Datenflüsse und Sicherheitsmechanismen der Plattform.

## 1. Konzeptionelle Architektur

KUKANILEA ist als **Local-First** Plattform konzipiert. Das bedeutet, dass die Primärdatenhaltung und Geschäftslogik lokal auf dem Endgerät oder im lokalen Netzwerk des Mandanten ausgeführt werden.

### App-Factory Pattern
Das Backend nutzt das Flask App-Factory-Pattern. Dies ermöglicht eine saubere Trennung von Konfiguration, Erweiterungen und Blueprints. Es erleichtert zudem das Testen, da für jede Test-Suite eine isolierte Instanz der Anwendung erstellt werden kann.

### Offline-First Paradigma
* **Daten-Souveränität:** Alle Geschäftsdaten verbleiben in lokalen SQLite-Datenbanken.
* **Resilienz:** Das System funktioniert ohne aktive Internetverbindung. Synchronisationsvorgänge (z.B. E-Mail-Import) werden asynchron und fehlertolerant behandelt.

## 2. Datenmodell & Persistenz

KUKANILEA setzt konsequent auf SQLite als Datenbank-Engine.

### SQLite Concurrency & WAL-Modus
Um hohe Performance bei gleichzeitigen Lese- und Schreibzugriffen zu gewährleisten, werden alle Datenbanken im **Write-Ahead Logging (WAL)** Modus betrieben. Dies verhindert Blocker bei Hintergrundprozessen (z.B. OCR-Scans).

### Trennung von Core und Auth
Das System nutzt eine strikte physische Trennung der Daten:
* **Auth-DB (`auth.sqlite3`):** Enthält Benutzerkonten, Rollen, Berechtigungen und Mandanten-Mapping.
* **Core-DB (`core.sqlite3`):** Enthält die eigentlichen Geschäftsdaten des Mandanten (Leads, CRM, Tasks, Dokumente).

## 3. Sicherheitsmodell

### Mandanten-Isolation (Tenant Scoping)
Jede Datenbankabfrage innerhalb der Core-DB ist zwingend an eine `tenant_id` gebunden. Dies wird auf Datenbankebene oder durch zentrale Middleware-Komponenten sichergestellt, um Cross-Tenant-Datenlecks zu verhindern.

### Read-Only Hook
Das System verfügt über einen globalen Read-Only-Modus. Dieser kann durch Lizenzbeschränkungen oder administrativ ausgelöst werden. In diesem Modus werden alle mutierenden Datenbankzugriffe unterbunden, während der Lesezugriff für den operativen Betrieb erhalten bleibt.

### Schutz vor Command-Injection
Alle Systemaufrufe (z.B. Tesseract OCR) nutzen strikt parameterbasierte Aufrufe ohne Shell-Execution, um Injection-Vektoren zu eliminieren.

## 4. Modul-Übersicht

* **Lead Intake:** Automatisierte Erfassung unstrukturierter Anfragen aus verschiedenen Quellen (E-Mail, Web).
* **CRM:** Strukturierte Verwaltung von Kunden, Projekten und Ansprechpartnern.
* **Omni-Hub:** Die zentrale Drehscheibe für die Datenaufbereitung und -anreicherung.
* **Automation Builder:** Ereignisgesteuerte Workflows zur Automatisierung repetitiver Aufgaben.

---

## 5. Prozessvisualisierung

### Datenfluss eines Leads durch den Omni-Hub

```mermaid
mermaid flowchart LR
    A[Unstrukturierter Lead] --> B[Omni-Hub Ingest]
    B --> C{OCR / Parsing}
    C --> D[Daten-Anreicherung]
    D --> E[Strukturierte Zuweisung]
    E --> F[CRM / Kundenakte]
```

### Architekturfluss des Automation Builders

```mermaid
mermaid flowchart LR
    T[Trigger] --> C{Allowlist Conditions}
    C -- Ja --> G[Human-in-the-loop Gate]
    G -- Freigabe --> A[Action]
    C -- Nein --> X[Abbruch]
    G -- Ablehnung --> X
```
