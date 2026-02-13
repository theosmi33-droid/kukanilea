from __future__ import annotations

from .core import (
    contacts_create,
    contacts_list_by_customer,
    customers_create,
    customers_get,
    customers_list,
    customers_update,
    deals_create,
    deals_list,
    deals_update_stage,
    emails_import_eml,
    quotes_add_item,
    quotes_create_from_deal,
    quotes_get,
)

__all__ = [
    "customers_create",
    "customers_get",
    "customers_list",
    "customers_update",
    "contacts_create",
    "contacts_list_by_customer",
    "deals_create",
    "deals_update_stage",
    "deals_list",
    "quotes_create_from_deal",
    "quotes_get",
    "quotes_add_item",
    "emails_import_eml",
]
