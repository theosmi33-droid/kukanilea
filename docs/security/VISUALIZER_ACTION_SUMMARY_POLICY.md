# Visualizer Action Summary Policy

Date: 2026-03-08

- Action summary must not read arbitrary filesystem paths.
- Requests outside configured/tenant-approved roots are rejected.
- Failures surface as safe error payloads, not raw path data.

