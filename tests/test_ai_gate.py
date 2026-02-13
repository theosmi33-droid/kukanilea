from __future__ import annotations

import importlib
import sys

import pytest

HEAVY_MODULES = [
    "chromadb",
    "sentence_transformers",
    "torch",
    "transformers",
    "tokenizers",
    "onnxruntime",
    "hnswlib",
    "numpy",
    "ollama",
]


def _loaded_prefixes() -> set[str]:
    prefixes = tuple(HEAVY_MODULES)
    return {name for name in sys.modules if name.startswith(prefixes)}


def test_ai_gate_does_not_import_heavy_deps_when_disabled(monkeypatch):
    monkeypatch.delenv("KUKA_AI_ENABLE", raising=False)

    for mod in ["app.ai", "app.ai.knowledge"]:
        sys.modules.pop(mod, None)

    before = _loaded_prefixes()
    import app.ai  # noqa: F401
    import app.ai.knowledge  # noqa: F401

    after = _loaded_prefixes()

    leaked = sorted(after - before)
    assert leaked == [], f"unexpected modules imported: {leaked}"


def test_ai_enabled_reports_actionable_missing_dependency(monkeypatch):
    monkeypatch.setenv("KUKA_AI_ENABLE", "1")

    import app.ai as ai

    importlib.reload(ai)

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package=None):
        if name in {"chromadb", "sentence_transformers", "ollama"}:
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(RuntimeError) as exc:
        ai.init_ai(None)

    msg = str(exc.value)
    assert "Install with:" in msg
    assert "pip install chromadb sentence-transformers ollama" in msg
