#!/usr/bin/env bash
set -euo pipefail

cat <<'UNIT'
[Unit]
Description=KUKANILEA Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/kukanilea
Environment=PORT=5051
Environment=KUKANILEA_SECRET=change-me
ExecStart=/opt/kukanilea/.venv/bin/python /opt/kukanilea/kukanilea_app.py
Restart=always
RestartSec=2
User=kukanilea
Group=kukanilea

[Install]
WantedBy=multi-user.target
UNIT
