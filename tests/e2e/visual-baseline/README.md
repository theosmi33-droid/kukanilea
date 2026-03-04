# UI visual baseline

Diese Baseline wird vom Playwright-Smoke `test_tools_navigation_smoke_with_visual_baseline`
pro Tool aktualisiert. Jede Datei `<tool>.png` ist der Referenzzustand für die 11 Haupt-Tools.

Aktualisieren (lokal):

```bash
PYENV_VERSION=3.12.12 python -m pytest tests/e2e/test_ui_workflow.py::test_tools_navigation_smoke_with_visual_baseline
```
