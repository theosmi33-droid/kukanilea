from .logic import *  # noqa: F403

# Re-export selected legacy internals for knowledge/* modules.
from . import logic as _logic

for _name in ("_effective_tenant", "_db", "_DB_LOCK", "TENANT_DEFAULT"):
    globals()[_name] = getattr(_logic, _name)
