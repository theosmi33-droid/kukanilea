from types import SimpleNamespace

from app.agents.base import AgentContext
from app.agents.orchestrator import Orchestrator


class _DummyLLM:
    def rewrite_query(self, _message: str):
        return {"intent": "unknown"}


def test_orchestrator_handles_hallo_without_search_fallback():
    core = SimpleNamespace(audit_log=None, task_create=None)
    orchestrator = Orchestrator(core, llm_provider=_DummyLLM())
    context = AgentContext(tenant_id="KUKANILEA", user="dev", role="DEV")

    result = orchestrator.handle("Hallo", context)

    assert result.intent == "smalltalk"
    assert "hallo" in result.text.lower() or "bereit" in result.text.lower()
    assert result.ok is True
