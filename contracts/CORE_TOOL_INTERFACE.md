# Core Tool Interface Contract

Version: 2026-03-06

All runtime tools in `app.tools.*` must satisfy this interface:

## Required attributes

- `name: str` — unique, non-empty tool id.
- `description: str` — human-readable description.
- `input_schema: dict` — JSON-schema-like input description.
- `run(...)` — callable execution entrypoint.
- `endpoints: list[str]` — non-empty list of absolute endpoint paths (each entry starts with `/`).

## Enforcement

- Enforcement entrypoint: `app.core.tool_loader.verify_tool_interface(tool)`.
- Loader entrypoint: `app.core.tool_loader.load_all_tools(app=None)`.
- `load_all_tools` validates each discovered tool and reports:
  - imported modules
  - loaded tools
  - failed modules
  - failed tools
- When a Flask app instance is provided, loader results are persisted into app config:
  - `TOOL_LOADER_REPORT`
  - `TOOL_LOADER_LOADED_TOOLS`
  - `TOOL_LOADER_FAILED_TOOLS`

## Notes

- `BaseTool.endpoints` defaults to `['/api/tools/<tool-name>']` to provide a consistent contract for existing tools.
- CLI verification is available via `python scripts/dev/verify_tools.py`.
