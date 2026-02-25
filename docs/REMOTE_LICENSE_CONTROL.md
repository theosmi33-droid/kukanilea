# KUKANILEA – Zentrale Lizenz-Steuerung (Excel-basiert)

Dieses Dokument beschreibt, wie Sie als KUKANILEA-Betreiber die Lizenzen Ihrer Kunden zentral und automatisiert über eine einfache Excel-Datei steuern können.

## 1. Das Konzept (Wie es funktioniert)
Jeder KUKANILEA-Kunde erhält bei der Installation eine einzigartige `Hardware-ID` (HWID). 
Anstatt Lizenzen mühsam manuell auf den Geräten der Kunden zu widerrufen, fragt das KUKANILEA-System beim Start (bzw. stündlich im Hintergrund) bei **Ihrem** zentralen Server an.

Dieser Server liest bei jeder Anfrage dynamisch Ihre `licenses.xlsx` Datei aus.
- Ist der Kunde auf `IsActive = True`, läuft KUKANILEA ganz normal weiter.
- Ist der Kunde auf `IsActive = False` (oder die HWID nicht vorhanden), sperrt sich KUKANILEA sofort auf dem Kunden-Rechner (Read-Only Modus).

## 2. Der zentrale Lizenz-Server (Ihr ZimaBlade)
Auf Ihrem eigenen Master-Gerät (NAS oder ZimaBlade im Büro) läuft ein leichtgewichtiger Server.

**Starten des Servers:**
```bash
cd /opt/kukanilea/license_server
python3 server.py
```
*(Wir empfehlen, diesen Server als `systemd` Service oder Docker-Container im Hintergrund laufen zu lassen).*

Die Datei `licenses.xlsx` liegt im selben Ordner. Sie können diese Datei jederzeit bearbeiten (z.B. neue Kunden hinzufügen oder abgelaufene Abos auf `IsActive = False` setzen). Der Server übernimmt die Änderungen in Echtzeit!

## 3. Wie der Kunde Ihr ZimaBlade erreicht (Netzwerk-Sicherheit)
Ihre Kunden haben wechselnde IP-Adressen und Sie möchten nicht Ihren Router für das ganze Internet öffnen (Port-Forwarding ist unsicher!).

**Die Lösung: Cloudflare Tunnel (Zero Trust)**
Ein Cloudflare Tunnel erstellt eine sichere, verschlüsselte Verbindung von Ihrem Lizenz-Server nach draußen, ohne dass Sie einen Port an Ihrem Router freigeben müssen.

1. Erstellen Sie einen kostenlosen Account bei Cloudflare (Zero Trust).
2. Installieren Sie `cloudflared` auf Ihrem ZimaBlade.
3. Verbinden Sie den lokalen Port `9090` mit einer Subdomain (z.B. `lizenz.ihre-firma.de`).

## 4. Konfiguration beim Kunden
Wenn Sie einem Kunden KUKANILEA ausliefern, konfigurieren Sie sein System in der `.env` Datei (oder beim Flashen) so, dass es auf Ihre Cloudflare-Subdomain zeigt:

```env
KUKANILEA_LICENSE_VALIDATE_URL="https://lizenz.ihre-firma.de/api/v1/license/validate"
```

Das war's! Das System des Kunden meldet sich ab sofort vollautomatisch bei Ihrer Excel-Datei. Fällt das Internet beim Kunden aus, greift das "Fail-Open"-Prinzip, sodass er weiterarbeiten kann, bis das Internet wieder da ist (keine Zwangssperre auf der Baustelle).
