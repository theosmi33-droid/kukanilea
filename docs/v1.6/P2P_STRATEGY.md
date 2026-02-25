# v1.6.0 Strategie-Memorandum: Local-Mesh-Sync (P2P)

**Datum:** Februar 2026
**Autor:** KUKANILEA Engineering

## Zielsetzung
Aufbau einer kollaborativen Multi-User Umgebung ohne Cloud-Server (Offline-First, Zero-Trust).
Zwei KUKANILEA-Instanzen (z. B. Meister auf Laptop, Geselle auf Tablet) sollen ihre SQLite-Datenbanken lokal im selben Netzwerk (WLAN/LAN) abgleichen können.

## Technologische Architektur

### 1. Discovery (mDNS/ZeroConf)
- Knoten (Nodes) finden sich automatisch im lokalen Netzwerk via Bonjour/Avahi.
- Keine IP-Eingabe erforderlich.

### 2. Transport-Sicherheit (mTLS)
- Alle Verbindungen werden über `TLS 1.3` gesichert.
- Einmaliges Geräte-Pairing via QR-Code (enthält Public Key und PIN) für gegenseitige Authentifizierung.
- Keine Daten verlassen das physische Netzwerk.

### 3. Datenbank-Synchronisation
- **Ansatz A: CRDTs (Conflict-free Replicated Data Types).** Nutzung von Bibliotheken wie `automerge` oder `yjs` für json-basierte Datenstrukturen.
- **Ansatz B: SQLite LiteSync / cr-sqlite.** Eine spezialisierte SQLite-Extension, die auf Tabellen-Ebene synct.
- *Entscheidung für v1.6.0:* Da wir relational speichern (Kontakte, Tasks), evaluieren wir `cr-sqlite` (Conflict-Free Replicated SQLite) für den Sync der operativen Tabellen.

## Herausforderungen & Limits
- Konfliktlösung bei gleichzeitiger Änderung am selben Datensatz (z.B. Task Status).
- Sync-Protokoll muss ressourcenschonend sein, um die UI-Performance nicht zu blockieren.
