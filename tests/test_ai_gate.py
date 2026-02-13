import sys


def test_ai_gate_does_not_import_heavy_deps_when_disabled(monkeypatch):
    monkeypatch.delenv("KUKA_AI_ENABLE", raising=False)

    for mod in ["chromadb", "sentence_transformers", "ollama", "app.ai"]:
        sys.modules.pop(mod, None)

    import app.ai  # noqa: F401

    for mod in ["chromadb", "sentence_transformers", "ollama"]:
        assert mod not in sys.modules, f"{mod} was imported but should not be"
