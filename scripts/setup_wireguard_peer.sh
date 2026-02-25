#!/bin/bash
# KUKANILEA v1.6.0 WireGuard Mesh Provisioning
# Generiert Schlüsselpaare und bereitet den verschlüsselten Tunnel vor.

set -e

WG_DIR="/etc/wireguard"
IFACE="kuka0"

echo "🔐 Starte WireGuard Mesh Handshake..."

# 1. WireGuard installieren falls nicht vorhanden
if ! command -v wg >/dev/null 2>&1; then
    sudo apt update && sudo apt install -y wireguard
fi

# 2. Schlüssel generieren
sudo mkdir -p $WG_DIR
sudo chmod 700 $WG_DIR

if [ ! -f "$WG_DIR/private.key" ]; then
    wg genkey | sudo tee $WG_DIR/private.key > /dev/null
    sudo cat $WG_DIR/private.key | wg pubkey | sudo tee $WG_DIR/public.key > /dev/null
    echo "✅ Neue Mesh-Schlüssel generiert."
else
    echo "ℹ️ Bestehende Schlüssel gefunden."
fi

PUB_KEY=$(sudo cat $WG_DIR/public.key)
echo "------------------------------------------------"
echo "IHR PUBLIC MESH KEY (Knoten-Einladung):"
echo "$PUB_KEY"
echo "------------------------------------------------"

# 3. Basis-Konfiguration (Vorschau)
# sudo tee $WG_DIR/$IFACE.conf > /dev/null <<EOF
# [Interface]
# PrivateKey = $(sudo cat $WG_DIR/private.key)
# Address = 10.0.8.1/24
# ListenPort = 51820
# EOF

echo "🚀 Hub ist bereit für Global Mesh Einladungen."
