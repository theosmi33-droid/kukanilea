from __future__ import annotations

from app import create_app

EXCLUDED_SUFFIXES = {
    "/claim",
    "/claim/force",
    "/release",
}


def test_all_mutating_lead_routes_are_guarded() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")

    missing: list[str] = []
    for rule in app.url_map.iter_rules():
        if not ({"POST", "PUT", "DELETE"} & set(rule.methods)):
            continue
        if not (rule.rule.startswith("/leads/") or rule.rule.startswith("/api/leads/")):
            continue
        if "<lead_id>" not in rule.rule:
            continue
        if any(rule.rule.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
            continue

        view = app.view_functions.get(rule.endpoint)
        if not getattr(view, "_requires_lead_access", False):
            missing.append(
                f"{rule.rule} [{','.join(sorted(rule.methods))}] -> {rule.endpoint}"
            )

    assert not missing, "Unguarded lead mutation routes:\n" + "\n".join(sorted(missing))
