# Backup/Restore Minimum für lokale Instanzen

Ziel: ein **kleiner, reproduzierbarer Ablauf** für Backup + Restore auf lokalen KUKANILEA-Instanzen, ohne neues Ops-Framework.

## Voraussetzungen

- Im Repo-Root ausführen.
- `instance/` existiert.
- Optional für NAS-Pfad: `smbclient`.
- Optional für komprimierte Archive: `zstd`.
- Optional für verschlüsselte Archive: `age` + Key.

## 1) Backup ausführen (lokal robust)

```bash
TENANT_ID=DEMO_TENANT \
REPORT_FILE=instance/operator_report_backup_minimum.txt \
bash scripts/ops/backup_to_nas.sh
```

Erwartung:
- Script liefert `mode=nas` **oder** fallback `mode=degraded_local`.
- Report enthält u. a. `backup_file`, `checksum_sha256`, `backup_size_bytes`, `target_path`, `backup_verify_hook`.

## 2) Restore ausführen (auf Basis letzter Sicherung)

```bash
TENANT_ID=DEMO_TENANT \
REPORT_FILE=instance/operator_report_restore_minimum.txt \
bash scripts/ops/restore_from_nas.sh
```

Erwartung:
- Restore prüft Integrität/Metadaten.
- Report enthält u. a. `verify_db=ok`, `verify_files=ok`, `restore_validation`, `restore_verify_hook`.

## 3) Mindest-Evidenz prüfen (Prüf-Helper)

Strikt (Produktionsziel):

```bash
python3 scripts/ops/check_backup_restore_reports.py \
  --backup-report instance/operator_report_backup_minimum.txt \
  --restore-report instance/operator_report_restore_minimum.txt
```

Warnungen erlauben (z. B. offline/degraded Umgebung):

```bash
python3 scripts/ops/check_backup_restore_reports.py \
  --backup-report instance/operator_report_backup_minimum.txt \
  --restore-report instance/operator_report_restore_minimum.txt \
  --allow-warn
```

## 4) Minimaler Review-Check

- Backup-Report: `mode`, `tenant_id`, `backup_file`, `target_path`, `checksum_sha256`, `backup_size_bytes` gesetzt.
- Restore-Report: `integrity_check`, `verify_db=ok`, `verify_files=ok`, `restore_validation` gesetzt.
- Bei `degraded_local`: Ursache (`degraded_reason`) dokumentieren und NAS später nachziehen.

## Hinweise

- Dieser Ablauf nutzt nur bestehende, projektinterne Skripte.
- Kein Umbau der Backup-Plattform, kein zusätzlicher Scheduler.
