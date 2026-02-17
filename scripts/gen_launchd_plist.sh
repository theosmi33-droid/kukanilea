#!/usr/bin/env bash
set -euo pipefail

cat <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.kukanilea.app</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>python3</string>
      <string>/Users/USERNAME/Tophandwerk/kukanilea-git/kukanilea_app.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PORT</key>
      <string>5051</string>
      <key>KUKANILEA_SECRET</key>
      <string>change-me</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/kukanilea.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/kukanilea.err.log</string>
  </dict>
</plist>
PLIST
