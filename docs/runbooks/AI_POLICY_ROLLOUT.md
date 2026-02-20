# AI Provider Policy Rollout

## Ziel

Mandanten-/rollenbasierte Steuerung der AI-Provider serverseitig erzwingen.

## 1) Policy-Preset schreiben

```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git
python scripts/apply_ai_policy_preset.py --preset reliability_max --print-env
```

Das schreibt standardmäßig:

`~/Library/Application Support/KUKANILEA/ai_provider_policy.json`

## 2) Policy aktivieren

In deiner Startumgebung setzen:

```bash
export KUKANILEA_AI_PROVIDER_POLICY_FILE="$HOME/Library/Application Support/KUKANILEA/ai_provider_policy.json"
```

## 3) Diagnose

```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git
python scripts/ai_provider_doctor.py --tenant KUKANILEA --roles READONLY,OPERATOR,ADMIN,DEV
```

## 4) Laufzeit-Check in der App

`GET /api/ai/status` enthält:
- `provider_specs` (nach Policy gefiltert)
- `provider_health`
- `provider_policy_effective`

## 5) Fail-closed Verhalten

Wenn Policy alle Provider für Rolle/Mandant blockt, liefert AI-Orchestrator:
- `status=ai_disabled`
- Hinweistext auf Policy

## Presets

- `local_only`: Nur lokale Provider
- `balanced`: Cloud nur für OPERATOR/ADMIN/DEV
- `reliability_max`: Maximale Verfügbarkeit mit lokal + cloud, restriktiv für READONLY
