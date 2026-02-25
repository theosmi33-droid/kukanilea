# KUKANILEA Knoten-Handbuch: ZimaBlade Setup

Diese Anleitung führt Sie durch die Einrichtung eines **Workshop-Hubs** auf dem ZimaBlade. Der Hub dient als zentraler Ankerpunkt für das Team-Mesh, sichert Daten lokal und übernimmt schwere KI-Berechnungen.

## 1. Hardware-Voraussetzungen
- **Gerät:** ZimaBlade (7300 oder 7700 Serie).
- **Speicher:** Interne eMMC (für OS) + externe SSD/HDD (für NAS-Vault).
- **Netzwerk:** Ethernet-Verbindung zum Werkstatt-Router bevorzugt.

## 2. Betriebssystem-Vorbereitung (OS)
Wir empfehlen ein schlankes **Debian 12** oder **Ubuntu Server 24.04 LTS**.

### Wichtige Pakete installieren:
```bash
sudo apt update && sudo apt install -y docker.io docker-compose python3-pip sqlite3 avahi-daemon clamav-daemon
```

## 3. KUKANILEA Hub Installation

1. **Repository klonen:**
   ```bash
   git clone https://github.com/tophandwerk/kukanilea-git.git /opt/kukanilea
   cd /opt/kukanilea
   ```

2. **Umgebung konfigurieren:**
   Erstellen Sie eine `.env` Datei:
   ```bash
   PORT=5051
   KUKANILEA_MODE=hub
   KUKANILEA_NAS_PATH=/mnt/nas_vault
   PRODUCT_NAME="KUKANILEA Hub"
   ```

3. **NAS-Partition mounten:**
   Stellen Sie sicher, dass Ihre externe Festplatte dauerhaft unter `/mnt/nas_vault` eingebunden ist (Eintrag in `/etc/fstab`).

## 4. Start im Hub-Modus
Der Hub läuft idealerweise als **Docker-Container**, um maximale Sicherheit (Read-Only Root) zu gewährleisten.

### Start via Docker Compose:
```bash
docker-compose -f docker/docker-compose.hub.yml up -d
```

Alternativ (nativ):
```bash
python3 run.py --hub --host 0.0.0.0 --port 5051
```

## 5. Mesh-Aktivierung & Pairing
Sobald der Hub läuft, ist er im lokalen WLAN via mDNS sichtbar.
1. Öffnen Sie die IP des Hubs im Browser eines Büro-Laptops.
2. Gehen Sie zu **Einstellungen > Team-Status**.
3. Der Hub erscheint als aktives Team-Mitglied.
4. Autorisieren Sie den Hub einmalig für den Delta-Sync.

## 6. Wartung & Thermik
Da das ZimaBlade lüfterlos ist, überwacht der Hub seine Temperatur selbstständig.
- **API-Check:** Rufen Sie `http://[HUB-IP]:5051/api/hub/vitals` auf, um die CPU-Temperatur zu prüfen.
- **Backup:** Das Skript `scripts/hub_backup_vault.sh` sollte via Cronjob stündlich ausgeführt werden.

---
*KUKANILEA Infrastructure | Version 1.5.0 Gold*
