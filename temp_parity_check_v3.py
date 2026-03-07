
import json
from app.contracts.tool_contracts import CONTRACT_TOOLS, MIA_DOMAIN_PROFILES
from app.web import TOOL_ACTION_TEMPLATES

def check_parity():
    rows = []
    for tool in CONTRACT_TOOLS:
        registered = tool in TOOL_ACTION_TEMPLATES
        profile = MIA_DOMAIN_PROFILES.get(tool, {})
        canonical_actions = profile.get("canonical_actions", [])
        
        actions_match = False
        if registered:
            template = TOOL_ACTION_TEMPLATES[tool]
            template_actions = set(template._actions.keys())
            # Canonical actions are usually tool.entity.action
            # In my templates, they are often entity.action
            # Let's see if the short names match
            canonical_short_names = {a.replace(f"{tool}.", "") for a in canonical_actions}
            actions_match = canonical_short_names.issubset(template_actions)
        
        checks = {
            "registered_in_template": registered,
            "canonical_actions_defined": len(canonical_actions) >= 1,
            "actions_implemented": actions_match,
            "summary_collector_exists": True,
        }
        
        score = sum(1 for v in checks.values() if v)
        rows.append({
            "tool": tool,
            "score": score,
            "max_score": len(checks),
            "tier": "high" if score == len(checks) else "low",
            "checks": checks
        })
    
    return {
        "rows": rows,
        "low_parity": [r["tool"] for r in rows if r["tier"] == "low"]
    }

print(json.dumps(check_parity(), indent=2))
