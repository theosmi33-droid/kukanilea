# Dashboard Owner Filter Policy

- Pending item queries must always bind to session owner context.
- Cross-owner aggregation is forbidden in default dashboard views.
- Any admin-wide view requires explicit role gate and audit event.
