from __future__ import annotations

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class PolicyEngine:
    def allows(self, role: str, required: str) -> bool:
        try:
            return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required)
        except ValueError:
            return False
