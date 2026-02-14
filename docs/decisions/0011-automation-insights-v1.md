# 0011 - Automation + Daily Insights v1

## Entscheidung
- Keine Hintergrundjobs in v1: Regeln werden nur on-demand ausgeführt.
- Conditions/Actions über strikte Allowlist statt freier Script-Engine.
- Harte Limits für Sicherheit und Determinismus:
  - max actions per run
  - max targets per rule

## Begründung
- Reduziert Sicherheitsfläche (kein Code-Exec, kein Netzwerk, kein Loop-Runaway).
- Stabiler Betrieb ohne Scheduler/Celery-Komplexität.
- Auditierbarkeit über `automation_runs`, `automation_run_actions`, Eventlog.

## Grenzen v1
- Kein Cron/Daemon.
- Keine externen Integrationen.
- DSL ist bewusst klein gehalten und wird später package-by-package erweitert.
