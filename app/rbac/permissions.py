from __future__ import annotations

from dataclasses import dataclass

LEGACY_ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]

SYSTEM_ROLES = ["OWNER_ADMIN", "BAULEITUNG", "OFFICE", "SUPPORT", "DEV"]


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    label: str
    description: str
    is_system: bool = True


@dataclass(frozen=True)
class PermissionDefinition:
    key: str
    label: str
    area: str


ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "OWNER_ADMIN": RoleDefinition(
        name="OWNER_ADMIN",
        label="Owner Admin",
        description="Kunden-Admin mit Einstellungen/Benutzerverwaltung.",
    ),
    "BAULEITUNG": RoleDefinition(
        name="BAULEITUNG",
        label="Bauleitung",
        description="Operative Rolle mit Schreibrechten in Kernmodulen.",
    ),
    "OFFICE": RoleDefinition(
        name="OFFICE",
        label="Office",
        description="Buerorolle mit typischen CRM/Tasks/Dokument-Rechten.",
    ),
    "SUPPORT": RoleDefinition(
        name="SUPPORT",
        label="Support",
        description="Eingeschraenkte Support-Rolle.",
    ),
    "DEV": RoleDefinition(
        name="DEV",
        label="Developer",
        description="Technische Rolle inklusive DEV/Update-Features.",
    ),
}


PERMISSION_DEFINITIONS: dict[str, PermissionDefinition] = {
    "settings.view": PermissionDefinition(
        key="settings.view", label="Settings anzeigen", area="settings"
    ),
    "settings.manage_permissions": PermissionDefinition(
        key="settings.manage_permissions",
        label="Berechtigungen verwalten",
        area="settings",
    ),
    "users.view": PermissionDefinition(
        key="users.view", label="Benutzer anzeigen", area="users"
    ),
    "users.assign_roles": PermissionDefinition(
        key="users.assign_roles", label="Rollen zuweisen", area="users"
    ),
    "crm.read": PermissionDefinition(key="crm.read", label="CRM lesen", area="crm"),
    "crm.write": PermissionDefinition(
        key="crm.write", label="CRM schreiben", area="crm"
    ),
    "tasks.read": PermissionDefinition(
        key="tasks.read", label="Tasks lesen", area="tasks"
    ),
    "tasks.write": PermissionDefinition(
        key="tasks.write", label="Tasks schreiben", area="tasks"
    ),
    "documents.read": PermissionDefinition(
        key="documents.read", label="Dokumente lesen", area="documents"
    ),
    "documents.write": PermissionDefinition(
        key="documents.write", label="Dokumente schreiben", area="documents"
    ),
    "workflows.read": PermissionDefinition(
        key="workflows.read", label="Workflows lesen", area="workflows"
    ),
    "workflows.write": PermissionDefinition(
        key="workflows.write", label="Workflows schreiben", area="workflows"
    ),
    "dev.update": PermissionDefinition(
        key="dev.update", label="Update Center", area="dev"
    ),
    "dev.tenant_meta": PermissionDefinition(
        key="dev.tenant_meta", label="Tenant-Metadaten", area="dev"
    ),
    "dev.tools": PermissionDefinition(key="dev.tools", label="DEV-Tools", area="dev"),
    "license.manage": PermissionDefinition(
        key="license.manage", label="Lizenz verwalten", area="license"
    ),
}


ROLE_PERMISSION_DEFAULTS: dict[str, set[str]] = {
    "DEV": {"*"},
    "OWNER_ADMIN": {
        "settings.view",
        "settings.manage_permissions",
        "users.view",
        "users.assign_roles",
        "crm.read",
        "crm.write",
        "tasks.read",
        "tasks.write",
        "documents.read",
        "documents.write",
        "workflows.read",
        "workflows.write",
        "license.manage",
    },
    "BAULEITUNG": {
        "settings.view",
        "crm.read",
        "crm.write",
        "tasks.read",
        "tasks.write",
        "documents.read",
        "documents.write",
        "workflows.read",
        "workflows.write",
    },
    "OFFICE": {
        "settings.view",
        "crm.read",
        "crm.write",
        "tasks.read",
        "tasks.write",
        "documents.read",
        "documents.write",
        "workflows.read",
    },
    "SUPPORT": {
        "settings.view",
        "crm.read",
        "tasks.read",
        "documents.read",
        "workflows.read",
    },
}


def normalize_role_name(value: str) -> str:
    token = str(value or "").strip().upper()
    if token in ROLE_DEFINITIONS:
        return token
    legacy = token if token in LEGACY_ROLE_ORDER else ""
    if legacy:
        return map_legacy_role_to_rbac(legacy)
    return token


def map_legacy_role_to_rbac(legacy_role: str) -> str:
    token = str(legacy_role or "").strip().upper()
    if token == "DEV":
        return "DEV"
    if token == "ADMIN":
        return "OWNER_ADMIN"
    if token == "OPERATOR":
        return "OFFICE"
    return "SUPPORT"


def legacy_role_from_roles(roles: list[str], fallback: str = "READONLY") -> str:
    mapped: list[str] = []
    for raw in roles:
        role = normalize_role_name(raw)
        if role == "DEV":
            mapped.append("DEV")
        elif role == "OWNER_ADMIN":
            mapped.append("ADMIN")
        elif role in {"BAULEITUNG", "OFFICE"}:
            mapped.append("OPERATOR")
        elif role == "SUPPORT":
            mapped.append("READONLY")
    if not mapped:
        fb = str(fallback or "READONLY").upper()
        return fb if fb in LEGACY_ROLE_ORDER else "READONLY"
    return max(mapped, key=lambda r: LEGACY_ROLE_ORDER.index(r))
