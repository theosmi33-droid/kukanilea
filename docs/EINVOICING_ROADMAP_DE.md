# EINVOICING_ROADMAP_DE

Date: 2026-02-21

## Purpose
Capture German e-invoicing readiness requirements for future invoice-related product modules.

## Regulatory Anchors (Germany / B2B)

- 2025-01-01: reception capability for B2B e-invoices required.
- Transition windows continue through 2027/2028 depending on case/turnover.
- EN 16931 baseline should guide format compatibility decisions.

## Product Impact for KUKANILEA

1. Define invoice data model with EN 16931-compatible fields.
2. Decide output formats (e.g. XRechnung/ZUGFeRD in later phases).
3. Add validation tests for mandatory semantic fields.
4. Define import/export audit logs and retention behavior.

## Release Gate Integration

- Current status: `BACKLOG` / not an RC blocker until invoicing feature scope is active.
- If invoicing is enabled in product scope, gate moves to mandatory compliance checks.

## Reference

- https://ec.europa.eu/digital-building-blocks/sites/display/DIGITAL/eInvoicing%2Bin%2BGermany
