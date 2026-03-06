# KUKANILEA Agent Fleet Registry

## Agent Roster

| Agent Name | Role | Primary Lane | Domain Expertise |
| :--- | :--- | :--- | :--- |
| **Kukanilea_UI** | Designer & UI Engineer | `runtime-ui` | dashboard, floating-widget, visualizer |
| **Kukanilea_Shield** | Security Architect | `security` | auth, session, rate-limit, gates |
| **Kukanilea_Builder** | CI/CD & Testing | `dev-ci` | tests, benchmarks, mock-data |
| **Kukanilea_Captain** | Ops & Release | `ops-release` | releases, backups, hardening |
| **Kukanilea_Contractor** | API & Contract Engineer | `domain-contracts` | upload, emailpostfach, messenger |
| **Kukanilea_Auto** | AI & Automation Specialist | `automation` | AI call intake, follow-up, workflow |
| **Kukanilea_Scribe** | Technical Writer | `docs-meta` | CHANGELOG, ROADMAP, ADRs |

## Operational Rules
1. Agents must only accept tasks from their primary lane.
2. If a task requires cross-lane coordination, it must be escalated to the `supervisor.py`.
3. Every agent is responsible for the healthchecks of their domain.
