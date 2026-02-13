from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, List

_core = import_module("kukanilea_core_v3_fixed")

customers_create = _core.customers_create
customers_get = _core.customers_get
customers_list = _core.customers_list
customers_update = _core.customers_update
contacts_create = _core.contacts_create
contacts_list_by_customer = _core.contacts_list_by_customer
deals_create = _core.deals_create
deals_update_stage = _core.deals_update_stage
deals_list = _core.deals_list
quotes_create_from_deal = _core.quotes_create_from_deal
quotes_get = _core.quotes_get
quotes_add_item = _core.quotes_add_item
emails_import_eml = _core.emails_import_eml


def deals_suggest_next_actions(tenant_id: str, deal_id: str) -> List[Dict[str, Any]]:
    """Default deterministic suggestions without AI dependency."""
    deal = _core.deals_list(tenant_id=tenant_id)
    current = next((d for d in deal if str(d.get("id")) == str(deal_id)), None)
    if not current:
        raise ValueError("deal_not_found")
    stage = str(current.get("stage") or "lead")
    if stage == "lead":
        return [{"action": "qualify_deal", "priority": "high"}]
    if stage == "qualified":
        return [{"action": "create_quote", "priority": "high"}]
    if stage == "proposal":
        return [{"action": "follow_up_call", "priority": "medium"}]
    if stage == "won":
        return [{"action": "handover_project", "priority": "medium"}]
    return [{"action": "archive_deal", "priority": "low"}]
