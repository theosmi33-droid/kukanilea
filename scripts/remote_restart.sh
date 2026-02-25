#!/bin/bash
# scripts/remote_restart.sh
# Automatisiertes Skript für den Remote-Server Neustart

set -e

APP_DIR="/opt/kukanilea"

echo "[START] Starting KUKANILEA Deployment..."

if [ ! -d "$APP_DIR" ]; then
  echo "[ERROR] Error: App directory $APP_DIR not found."
  exit 1
fi

cd "$APP_DIR"

echo "📥 Pulling latest images..."
docker-compose pull

echo "♻️ Restarting containers..."
docker-compose up -d --remove-orphans

echo "🧹 Cleaning up old images..."
docker image prune -f

echo "[SUCCESS] KUKANILEA is up and running!"
