from __future__ import annotations

import json

from app.ai.policy import filter_provider_specs, load_provider_policy
from app.ai.provider_router import ProviderSpec, provider_specs_from_env


def test_policy_tenant_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "vllm,ollama")
    monkeypatch.setenv(
        "KUKANILEA_AI_PROVIDER_POLICY_JSON",
        json.dumps({"tenants": {"TENANT_A": {"allow_providers": ["vllm"]}}}),
    )
    specs = provider_specs_from_env(tenant_id="TENANT_A", role="OFFICE")
    assert [s.provider_type for s in specs] == ["vllm"]


def test_policy_blocks_cloud_for_role(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "ollama,groq,anthropic")
    monkeypatch.setenv(
        "KUKANILEA_AI_PROVIDER_POLICY_JSON",
        json.dumps({"roles": {"OFFICE": {"allow_cloud": False}}}),
    )
    specs = provider_specs_from_env(tenant_id="KUKANILEA", role="OFFICE")
    assert [s.provider_type for s in specs] == ["ollama"]


def test_policy_blocked_role_all_denied(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "ollama,vllm")
    monkeypatch.setenv(
        "KUKANILEA_AI_PROVIDER_POLICY_JSON",
        json.dumps({"default": {"blocked_roles": ["SUPPORT"]}}),
    )
    specs = provider_specs_from_env(tenant_id="KUKANILEA", role="support")
    assert specs == []


def test_filter_provider_specs_unknown_safe_default() -> None:
    # unknown provider treated as cloud -> denied when cloud disabled.
    specs = [
        ProviderSpec(
            provider_type="unknown_provider", priority=1, base_url="", model=""
        )
    ]
    policy = {"default": {"allow_cloud": False}}
    out = filter_provider_specs(
        specs=specs, tenant_id="KUKANILEA", role="OFFICE", policy=policy
    )
    assert out == []


def test_load_policy_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_POLICY_JSON", "{bad-json")
    assert load_provider_policy() == {}
