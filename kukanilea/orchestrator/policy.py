from __future__ import annotations

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class PolicyEngine:
    def normalize_role(self, role: str) -> str:
        role = (role or "").upper()
        return role if role in ROLE_ORDER else ""

    def allows(self, role: str, required: str) -> bool:
        role = self.normalize_role(role)
        required = self.normalize_role(required)
        if not role or not required:
            return False
        return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required)

    def policy_check(self, role: str, tenant: str, action: str, scope: str) -> bool:
        role = self.normalize_role(role)
        if not tenant or not role:
            return False
        action_name = (action or "").strip()

        from app.tools.action_registry import action_registry

        # Match against registry instead of hardcoded list
        matches = action_registry.search(action_name)
        if not matches:
            # Fallback for short names
            matches = [a for a in action_registry.list_actions() if a["name"].startswith(f"{action_name}.")]

        if not matches:
            return False

        # If any matching action is allowed for this role, we allow it
        for act in matches:
            required_role = "OPERATOR" if act.get("permissions", ["write"])[0] == "write" else "READONLY"
            if act.get("risk_level") == "HIGH":
                required_role = "ADMIN"
            
            # DEBUG
            # print(f"Checking {act['name']}: risk={act.get('risk_level')} req={required_role} has={role} allows={self.allows(role, required_role)}")

            if self.allows(role, required_role):
                return True

        return False
