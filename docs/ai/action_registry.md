# Action Registry Framework

The Action Registry standardizes tool capabilities as typed actions:

- `name`
- `inputs_schema`
- `permissions`
- `is_critical`
- `audit_fields`

## Architecture

- `BaseTool.actions()` now emits a standardized action set (22 actions per tool by default).
- `ToolRegistry.register()` auto-registers these actions into `ActionRegistry`.
- `ActionManager` allows manager-agent capabilities:
  - list actions
  - search/filter actions
  - compose multi-step workflows
  - emit event descriptors for composed actions

## Catalog generation

Run:

```bash
python scripts/ops/action_registry_catalog.py
```

Outputs:

- JSON catalog in `evidence/operations/action_catalog.json`
- Markdown catalog in `docs/ai/action_registry_catalog.md`

This is intended as the baseline compliance check for large action inventories.
