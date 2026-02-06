from __future__ import annotations

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class PolicyEngine:
    ACTION_ALLOWLIST = {
        "READONLY": {"search_docs", "open_token"},
        "OPERATOR": {"search_docs", "open_token", "show_customer"},
        "ADMIN": {"search_docs", "open_token", "show_customer", "summarize_doc", "list_tasks"},
        "DEV": {"search_docs", "open_token", "show_customer", "summarize_doc", "list_tasks", "rebuild_index"},
    }

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
        action = (action or "").strip()
        allowed = self.ACTION_ALLOWLIST.get(role, set())
        return action in allowed
