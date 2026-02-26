#!/bin/bash
# scripts/ops/setup_hub.sh
# KUKANILEA Hub Provisioning Script
# Target: Debian/Ubuntu (ZimaBlade)
# Purpose: Transforms a fresh ZimaBlade into a production-ready KUKANILEA Hub.

set -e

echo "🚀 Starting KUKANILEA Hub Provisioning..."

# 1. Update & Basic Tools
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git python3 python3-pip python3-venv sqlite3 htop jq

# 2. Install Docker
echo "🐳 Installing Docker Engine..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed."
else
    echo "✅ Docker already present."
fi

# 3. Install Ollama (Local AI)
echo "🧠 Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✅ Ollama installed."
else
    echo "✅ Ollama already present."
fi

# 4. Install Tailscale (Zero-Trust Mesh)
echo "📡 Installing Tailscale..."
if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
    sudo tailscale up --authkey=$TAILSCALE_AUTHKEY # Requires TAILSCALE_AUTHKEY in env
    echo "✅ Tailscale active."
else
    echo "✅ Tailscale already present."
fi

# 5. Application Setup
echo "🏗️ Setting up KUKANILEA environment..."
PROJECT_DIR="$HOME/kukanilea"
mkdir -p "$PROJECT_DIR"
# Assuming the tarball was uploaded here
# tar -xzf kukanilea-v1.7.0-zimablade.tar.gz -C "$PROJECT_DIR" --strip-components=1

# 6. Database Optimization (WAL Mode)
DB_PATH="$PROJECT_DIR/instance/kukanilea.db"
mkdir -p "$(dirname "$DB_PATH")"
if [ ! -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" "VACUUM;"
fi
echo "⚙️ Configuring SQLite WAL-Mode..."
sqlite3 "$DB_PATH" "PRAGMA journal_mode=WAL;"
sqlite3 "$DB_PATH" "PRAGMA synchronous=NORMAL;"

# 7. Systemd Service Creation
echo "🔄 Creating Systemd Service..."
cat <<EOF | sudo tee /etc/systemd/system/kukanilea.service
[Unit]
Description=KUKANILEA Enterprise Hub
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR
ExecStart=/usr/bin/python3 $PROJECT_DIR/run.py server --port 5051 --host 0.0.0.0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
# sudo systemctl enable kukanilea
# sudo systemctl start kukanilea

echo "🎉 Provisioning Complete! Hub is ready."
echo "Access via: http://$(hostname -I | awk '{print $1}'):5051"
