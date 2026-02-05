from __future__ import annotations

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class PolicyEngine:
    def normalize_role(self, role: str) -> str:
        role = (role or "READONLY").upper()
        return role if role in ROLE_ORDER else "READONLY"

    def allows(self, role: str, required: str) -> bool:
        role = self.normalize_role(role)
        required = self.normalize_role(required)
        return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required)

    def policy_check(self, role: str, tenant: str, action: str, scope: str) -> bool:
        _ = tenant, action, scope
        return self.allows(role, "READONLY")
