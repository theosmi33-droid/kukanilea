import inspect

from kukanilea.contracts import ChatResponseContract
from kukanilea.orchestrator.intent import IntentParser
from kukanilea.orchestrator.orchestrator import OrchestratorResult


def test_intent_parser_signature():
    sig = inspect.signature(IntentParser.parse)
    assert "allow_llm" in sig.parameters
    assert sig.parameters["allow_llm"].default is True


def test_orchestrator_result_fields():
    result = OrchestratorResult(
        text="ok",
        actions=[],
        intent="search",
        data={},
        suggestions=[],
        ok=True,
        error=None,
    )
    assert hasattr(result, "suggestions")
    assert hasattr(result, "ok")
    assert hasattr(result, "error")


def test_chat_response_contract_error():
    payload = {
        "ok": False,
        "message": "Fehler",
        "suggestions": [],
        "results": [],
        "actions": [],
        "error": {"code": "test", "message": "Fehler", "details": {"request_id": "123"}},
    }
    contract = ChatResponseContract.from_payload(payload)
    assert contract.error is not None
    assert contract.error.code == "test"
