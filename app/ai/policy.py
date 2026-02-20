from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
from typing import Any

LOCAL_PROVIDER_TYPES = {"ollama", "vllm", "lmstudio", "lm_studio"}
CLOUD_PROVIDER_TYPES = {
    "groq",
    "anthropic",
    "gemini",
    "openai_compat",
    "openai_compat_fallback",
    "openai-compatible",
    "openai-compatible-fallback",
}


def _norm_str(value: Any) -> str:
    return str(value or "").strip()


def _norm_key(value: Any) -> str:
    return _norm_str(value).upper()


def _as_list(value: Any, *, upper: bool = False) -> list[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw = [str(item or "").strip() for item in value]
    else:
        raw = []
    out: list[str] = []
    for row in raw:
        if not row:
            continue
        normalized = row.upper() if upper else row.lower()
        if normalized not in out:
            out.append(normalized)
    return out


def _normalize_rule(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    out: dict[str, Any] = {}
    if "allow_providers" in row:
        out["allow_providers"] = _as_list(row.get("allow_providers"))
    if "deny_providers" in row:
        out["deny_providers"] = _as_list(row.get("deny_providers"))
    if "allowed_roles" in row:
        out["allowed_roles"] = _as_list(row.get("allowed_roles"), upper=True)
    if "blocked_roles" in row:
        out["blocked_roles"] = _as_list(row.get("blocked_roles"), upper=True)
    if "allow_local" in row:
        out["allow_local"] = bool(row.get("allow_local"))
    if "allow_cloud" in row:
        out["allow_cloud"] = bool(row.get("allow_cloud"))
    return out


def _merge_rule(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key in (
        "allow_providers",
        "deny_providers",
        "allowed_roles",
        "blocked_roles",
        "allow_local",
        "allow_cloud",
    ):
        if key in override:
            out[key] = override[key]
    return out


def load_provider_policy() -> dict[str, Any]:
    raw = _norm_str(os.environ.get("KUKANILEA_AI_PROVIDER_POLICY_JSON"))
    if raw:
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    path_raw = _norm_str(os.environ.get("KUKANILEA_AI_PROVIDER_POLICY_FILE"))
    if not path_raw:
        return {}
    path = Path(path_raw).expanduser()
    if not path.exists() or not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def provider_category(provider_type: str, base_url: str = "") -> str:
    ptype = _norm_str(provider_type).lower()
    if ptype in LOCAL_PROVIDER_TYPES:
        return "local"
    if ptype in CLOUD_PROVIDER_TYPES:
        if ptype.startswith("openai_compat") or ptype.startswith("openai-compatible"):
            host = _norm_str(urllib.parse.urlparse(base_url).hostname).lower()
            if host in {"127.0.0.1", "localhost", "::1"}:
                return "local"
        return "cloud"
    # Unknown provider defaults to cloud (fail-closed for local-only policies).
    return "cloud"


def resolve_effective_rule(
    *,
    policy: dict[str, Any] | None,
    tenant_id: str | None,
    role: str | None,
) -> dict[str, Any]:
    policy_obj = policy if isinstance(policy, dict) else load_provider_policy()
    rule: dict[str, Any] = {}
    rule = _merge_rule(rule, _normalize_rule(policy_obj.get("default")))

    tenant_key = _norm_key(tenant_id)
    role_key = _norm_key(role)

    tenants = policy_obj.get("tenants")
    if isinstance(tenants, dict):
        if "*" in tenants:
            rule = _merge_rule(rule, _normalize_rule(tenants.get("*")))
        if tenant_key and tenant_key in {_norm_key(k): k for k in tenants.keys()}:
            original = next(
                (k for k in tenants.keys() if _norm_key(k) == tenant_key), None
            )
            if original is not None:
                rule = _merge_rule(rule, _normalize_rule(tenants.get(original)))

    roles = policy_obj.get("roles")
    if isinstance(roles, dict) and role_key:
        if role_key in {_norm_key(k): k for k in roles.keys()}:
            original = next((k for k in roles.keys() if _norm_key(k) == role_key), None)
            if original is not None:
                rule = _merge_rule(rule, _normalize_rule(roles.get(original)))

    tenant_roles = policy_obj.get("tenant_roles")
    if isinstance(tenant_roles, dict) and tenant_key and role_key:
        tenant_bucket_key = next(
            (k for k in tenant_roles.keys() if _norm_key(k) == tenant_key),
            None,
        )
        if tenant_bucket_key is not None:
            tenant_bucket = tenant_roles.get(tenant_bucket_key)
            if isinstance(tenant_bucket, dict):
                role_bucket_key = next(
                    (k for k in tenant_bucket.keys() if _norm_key(k) == role_key),
                    None,
                )
                if role_bucket_key is not None:
                    rule = _merge_rule(
                        rule, _normalize_rule(tenant_bucket.get(role_bucket_key))
                    )
    return rule


def effective_rule_public(
    *,
    tenant_id: str | None,
    role: str | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return resolve_effective_rule(policy=policy, tenant_id=tenant_id, role=role)


def is_provider_allowed(
    *,
    provider_type: str,
    base_url: str,
    tenant_id: str | None,
    role: str | None,
    policy: dict[str, Any] | None = None,
) -> bool:
    rule = resolve_effective_rule(policy=policy, tenant_id=tenant_id, role=role)
    provider = _norm_str(provider_type).lower()
    role_key = _norm_key(role)

    allowed_roles = rule.get("allowed_roles")
    if isinstance(allowed_roles, list) and allowed_roles:
        if role_key not in {str(v).upper() for v in allowed_roles}:
            return False

    blocked_roles = rule.get("blocked_roles")
    if isinstance(blocked_roles, list) and blocked_roles:
        if role_key in {str(v).upper() for v in blocked_roles}:
            return False

    allow_providers = rule.get("allow_providers")
    if isinstance(allow_providers, list) and allow_providers:
        if provider not in {str(v).lower() for v in allow_providers}:
            return False

    deny_providers = rule.get("deny_providers")
    if isinstance(deny_providers, list) and provider in {
        str(v).lower() for v in deny_providers
    }:
        return False

    category = provider_category(provider, base_url=base_url)
    if category == "local" and rule.get("allow_local") is False:
        return False
    if category == "cloud" and rule.get("allow_cloud") is False:
        return False
    return True


def filter_provider_specs(
    *,
    specs: list[Any],
    tenant_id: str | None,
    role: str | None,
    policy: dict[str, Any] | None = None,
) -> list[Any]:
    out: list[Any] = []
    for row in list(specs or []):
        provider_type = _norm_str(getattr(row, "provider_type", "")).lower()
        base_url = _norm_str(getattr(row, "base_url", ""))
        if not provider_type:
            continue
        if is_provider_allowed(
            provider_type=provider_type,
            base_url=base_url,
            tenant_id=tenant_id,
            role=role,
            policy=policy,
        ):
            out.append(row)
    return out
