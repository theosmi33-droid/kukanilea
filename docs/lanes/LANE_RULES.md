# KUKANILEA Lane Discipline & Ownership

## Lane Definitions

| Lane | Focus | Ownership Scope |
| :--- | :--- | :--- |
| **runtime-ui** | Frontend, UX, Templates | `app/templates/`, `app/static/`, `app/routes/` (GET only) |
| **security** | Hardening, Auth, Gates | `app/security/`, `app/auth.py`, `app/core/security.py` |
| **dev-ci** | Tooling, Testing, DX | `tests/`, `scripts/dev_`, `pytest.ini` |
| **ops-release** | Deployment, Backups, Scaling | `scripts/ops/`, `run_enterprise_hardening.sh`, `PACKAGING.md` |
| **domain-contracts** | APIs, Schemas, Tools | `app/contracts/`, `app/tools/`, `app/api.py` |
| **automation** | AI, Agents, Background Jobs | `app/agents/`, `app/ai/`, `app/core/automation.py` |
| **docs-meta** | Documentation, ADRs, Reports | `docs/`, `README.md`, `status_report.md` |

## CORE_OWNED Files (Strict Isolation)
Changes to these files require a `scope_request_required=true` and manual review by the Program Director.

- `app/web.py`: Main application factory and middleware.
- `app/db.py`: Database engine and connection pooling.
- `app/config.py`: System-wide configuration.
- `app/auth.py`: Central authentication logic.
- `app/api.py`: Main API router and dispatcher.
- `app/core/boot_sequence.py`: Initialization logic.
- `app/security/gates.py`: Global security interceptors.
- `app/agents/supervisor.py`: Agent coordination logic.
- `app/errors.py`: Global error handling and logging.
- `app/lifecycle.py`: Application startup/shutdown hooks.

## Overlap Rules
1. **No Shared File Scope**: Two tasks in different lanes cannot modify the same file unless it is a `CORE_OWNED` file.
2. **Atomic Commits**: Every task must result in a clean PR.
3. **Verification**: If a UI task touches a route, it must not break the contract defined by the `domain-contracts` lane.
