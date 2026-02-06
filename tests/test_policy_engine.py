from kukanilea.orchestrator.policy import PolicyEngine


def test_policy_denies_without_tenant():
    policy = PolicyEngine()
    assert policy.policy_check("ADMIN", "", "open_token", "search") is False


def test_policy_denies_unknown_role():
    policy = PolicyEngine()
    assert policy.policy_check("UNKNOWN", "KUKANILEA", "open_token", "search") is False


def test_policy_allows_known_role():
    policy = PolicyEngine()
    assert policy.policy_check("READONLY", "KUKANILEA", "open_token", "search") is True
