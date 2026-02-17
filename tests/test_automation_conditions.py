from __future__ import annotations

from app.automation.conditions import (
    canonicalize_condition_config,
    evaluate_conditions,
)


def test_conditions_basic_operators_positive_negative() -> None:
    ctx = {
        "event_type": "email.received",
        "from_domain": "sales@example.com",
        "count": "3",
    }
    assert (
        evaluate_conditions(
            {"field": "event_type", "equals": "email.received"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "event_type", "not_equals": "lead.created"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "from_domain", "contains": "@example.com"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "from_domain", "not_contains": "@internal"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "from_domain", "starts_with": "sales"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "from_domain", "ends_with": ".com"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "event_type", "equals": "lead.created"},
            ctx,
            allowed_fields=["event_type", "from_domain", "count"],
        )
        is False
    )


def test_conditions_present_and_nested_all_any() -> None:
    ctx = {
        "event_type": "email.received",
        "from_domain": "sales@example.com",
        "empty": "",
    }
    assert (
        evaluate_conditions(
            {"field": "from_domain", "present": True},
            ctx,
            allowed_fields=["event_type", "from_domain", "empty"],
        )
        is True
    )
    assert (
        evaluate_conditions(
            {"field": "empty", "present": True},
            ctx,
            allowed_fields=["event_type", "from_domain", "empty"],
        )
        is False
    )
    assert (
        evaluate_conditions(
            {
                "all": [
                    {"field": "event_type", "equals": "email.received"},
                    {
                        "any": [
                            {"field": "from_domain", "contains": "example"},
                            {"field": "from_domain", "contains": "invalid"},
                        ]
                    },
                ]
            },
            ctx,
            allowed_fields=["event_type", "from_domain", "empty"],
        )
        is True
    )


def test_conditions_unknown_operator_and_field_allowlist() -> None:
    ctx = {"event_type": "email.received", "secret_token": "abc"}
    assert (
        evaluate_conditions(
            {"field": "event_type", "regex": ".*"},
            ctx,
            allowed_fields=["event_type"],
        )
        is False
    )
    assert (
        evaluate_conditions(
            {"field": "secret_token", "equals": "abc"},
            ctx,
            allowed_fields=["event_type"],
        )
        is False
    )


def test_condition_canonicalization_is_stable() -> None:
    config_a = {"all": [{"field": "a", "equals": "1"}, {"field": "b", "contains": "x"}]}
    config_b = {"all": [{"equals": "1", "field": "a"}, {"contains": "x", "field": "b"}]}
    assert canonicalize_condition_config(config_a) == canonicalize_condition_config(
        config_b
    )
