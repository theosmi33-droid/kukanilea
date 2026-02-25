#!/bin/bash
# KUKANILEA Node-Flasher v1.5.0 Gold
# Automatisiertes Setup für neue ZimaBlade Hardware-Appliances.

set -e

# Farben für CLI
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}🚀 KUKANILEA Node-Flasher gestartet...${NC}"

# 1. Parameter-Check
KUNDE_NAME=${1:-"Standard Handwerker"}
PRODUCT_ID=${2:-"KUKA-HUB-$(date +%s)"}

echo "🛠️ Bereite Knoten vor für: $KUNDE_NAME ($PRODUCT_ID)"

# 2. Abhängigkeiten installieren
echo "📦 Installiere System-Kernkomponenten..."
sudo apt update -qq && sudo apt install -y -qq 
    docker.io docker-compose git avahi-daemon clamav-daemon ufw sqlite3 > /dev/null

# 3. KUKANILEA Repository vorbereiten
if [ ! -d "/opt/kukanilea" ]; then
    echo "📂 Klone Gold-Repository..."
    sudo git clone https://github.com/tophandwerk/kukanilea-git.git /opt/kukanilea
fi
cd /opt/kukanilea

# 4. Kunden-Branding injizieren (White-Labeling)
echo "🎨 Injiziere Kunden-Konfiguration..."
sudo tee .env > /dev/null <<EOF
PORT=5051
KUKANILEA_MODE=hub
KUKANILEA_PRODUCT_NAME="$KUNDE_NAME Hub"
KUKANILEA_INSTANCE_ID="$PRODUCT_ID"
KUKANILEA_NAS_PATH=/mnt/nas_vault
KUKANILEA_TESTING=0
EOF

# 5. Security: Firewall-Härtung (Zero-Trust)
echo "🛡️ Aktiviere Firewall-Schutzschild..."
sudo ufw default deny incoming > /dev/null
sudo ufw allow 22/tcp > /dev/null
sudo ufw allow 5051/tcp > /dev/null
sudo ufw allow 5353/udp > /dev/null # Mesh Discovery
sudo ufw --force enable > /dev/null

# 6. Docker Hub starten
echo "🐳 Starte gehärtetes Docker-Deployment..."
sudo docker-compose -f docker/docker-compose.hub.yml pull
sudo docker-compose -f docker/docker-compose.hub.yml up -d

# 7. Abschluss
echo -e "${GREEN}✅ KUKANILEA KNOTEN ERFOLGREICH GEFLASHED!${NC}"
echo "------------------------------------------------"
echo "IP-ADRESSE: $(hostname -I | awk '{print $1}')"
echo "PORT: 5051"
echo "KUNDE: $KUNDE_NAME"
echo "------------------------------------------------"
