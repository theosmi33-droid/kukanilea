# Visualizer Tenant Path Policy

## Rule
Visualizer endpoints may only access files inside the current tenant subtree.

## Enforcement Points
- `/api/visualizer/render`
- `/api/visualizer/summary`

## Validation
- Path is resolved and checked against known visualizer roots.
- First path segment under root must match normalized session tenant key.
- Violations return `403 forbidden_tenant_path`.
