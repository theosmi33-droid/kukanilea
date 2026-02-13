# KUKANILEA Operations (Always-On)

## Runtime model
- Local-first Flask app behind Waitress.
- Offline-first default (no required external network).
- Health endpoints:
  - `GET /api/health/live` -> process liveness only
  - `GET /api/health/ready` -> runtime-readiness checks (read-only)

## Linux (systemd)
Generate template:
```bash
bash scripts/gen_systemd_unit.sh > kukanilea.service
```
Install:
```bash
sudo cp kukanilea.service /etc/systemd/system/kukanilea.service
sudo systemctl daemon-reload
sudo systemctl enable --now kukanilea.service
```
Rollback:
```bash
sudo systemctl stop kukanilea.service
# deploy previous artifact
sudo systemctl start kukanilea.service
```

## macOS (launchd)
Generate template:
```bash
bash scripts/gen_launchd_plist.sh > com.kukanilea.app.plist
```
Install:
```bash
cp com.kukanilea.app.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.kukanilea.app.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.kukanilea.app.plist
```
Rollback:
```bash
launchctl unload ~/Library/LaunchAgents/com.kukanilea.app.plist
# deploy previous artifact
launchctl load ~/Library/LaunchAgents/com.kukanilea.app.plist
```

## Windows (Service)
Generate command script:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/gen_windows_service.ps1 > windows_service_commands.txt
```
Apply (Admin PowerShell):
```powershell
# Review generated commands first
```
Rollback:
```powershell
sc.exe stop KUKANILEA
# deploy previous artifact
sc.exe start KUKANILEA
```

## Mobile access
- Use browser/PWA from mobile over LAN or VPN.
- Bind host conservatively; avoid public exposure without reverse proxy and TLS.
- Keep authentication enabled; do not expose admin interfaces publicly.

## Availability notes
- Target uptime: 99.8% with process supervision + restart policy.
- Updates should use brief maintenance windows; validate readiness endpoint after deployment.

## Tenant uniqueness limitation
- Tenant-scoped unique indexes are enabled for `emails_cache(tenant_id, message_id)` and `quotes(tenant_id, quote_number)`.
- If older deployments had stricter/global uniqueness constraints, they are preserved to avoid destructive migrations.
