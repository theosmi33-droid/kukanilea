# Visualizer Source ID Escape Policy

- Any source identifier rendered into HTML attributes must be escaped first.
- Raw identifier interpolation into `data-*` attributes is forbidden.
- Regression tests must guard template-level escape bindings.
