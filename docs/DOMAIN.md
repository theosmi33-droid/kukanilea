# Domain Glossary

## Tenants
- Tenant comes from membership; UI never accepts user input for tenant selection.
- All reads/writes must be tenant-scoped.

## Pipeline
States: RECEIVED → STORED → EXTRACTED → ENRICHED → INDEXED → ARCHIVED.

## Invariants
- DB is the source of truth.
- Filesystem is the execution surface.
- Deny-by-default policy + audit trail.
