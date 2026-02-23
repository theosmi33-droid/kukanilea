# KUKANILEA v2.0 - Peer-to-Peer Sync (Cloudless)

## Vision
Handwerksbetriebe arbeiten oft mit mehreren Geräten (Büro-PC, Tablet auf Baustelle). v2.0 ermöglicht eine nahtlose Synchronisation ohne Internetabhängigkeit und ohne zentrale Cloud.

## 1. Discovery (mDNS / Zeroconf)
- Instanzen finden sich automatisch im selben Subnetz (WLAN).
- Dienstname: `_kukanilea._tcp.local.`

## 2. Security (E2EE Pairing)
- Die erste Verbindung muss manuell bestätigt werden (z.B. Vergleich eines 6-stelligen Codes oder QR-Scan).
- Alle Datenpakete werden mit AES-256 (GCM) verschlüsselt, wobei die Schlüssel nur auf den Geräten liegen (Zero-Knowledge).

## 3. Synchronisation (Differential Sync)
- **Vektor-Abgleich:** Merkle-Trees werden genutzt, um Unterschiede in der SQLite-Datenbank effizient zu finden.
- **Konfliktlösung:** Last-Write-Wins (LWW) mit optionaler manueller Korrektur im Dev-Dashboard.
- **Large Files:** Dokumente und Bilder werden über segmentierte Chunks übertragen.

## 4. Anwendungsfall: Messe-Mesh
Für die Messe-Präsentation können zwei Laptops nebeneinander stehen. Änderungen an Kunden auf Laptop A erscheinen ohne Cloud-Verzögerung auf Laptop B.
