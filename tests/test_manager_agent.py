from app.agents.manager_agent import route_via_manager_agent


def test_manager_agent_routes_and_marks_critical_actions():
    def _answer(_msg: str, role: str = "USER"):
        assert role == "DEV"
        return {
            "text": "ok",
            "actions": [{"type": "create_task", "title": "A"}],
            "data": {"hub": {"react_trace": [{"action": "search_docs", "observation": {"hits": 1}}]}},
        }

    result = route_via_manager_agent("bitte aufgabe erstellen", role="DEV", answer_fn=_answer)
    body = result.response

    assert body["requires_confirm"] is True
    assert body["manager_agent"]["route"] == "manager_agent"
    assert body["manager_agent"]["proposed_actions"][0]["proposed"] is True
    assert body["manager_agent"]["proposed_actions"][0]["confirm_required"] is True
    assert body["manager_agent"]["plan"]
    assert body["manager_agent"]["progress"]["total_steps"] >= 1


def test_manager_agent_extracts_object_refs_from_response_and_actions():
    def _answer(_msg: str, role: str = "USER"):
        return {
            "text": "done",
            "task_id": 7,
            "data": {"email_id": "em-1"},
            "actions": [{"type": "search_docs", "event_id": "ev-2"}],
        }

    result = route_via_manager_agent("zeige refs", role="USER", answer_fn=_answer)
    refs = result.response["manager_agent"]["object_refs"]
    assert refs["task_id"] == ["7"]
    assert refs["event_id"] == ["ev-2"]
    assert refs["email_id"] == ["em-1"]
