from __future__ import annotations

from app.core.mia_cross_tool_flows import MIA_FLOW_AUDIT_EVENT_MATRIX, MiaFlowEngine


def test_flow_catalog_contains_roi_flows() -> None:
    engine = MiaFlowEngine()
    flows = engine.list_flows()
    assert len(flows) == 9
    assert {flow["flow_id"] for flow in flows} == {
        "inquiry_to_task_project_calendar_proposal",
        "email_to_task",
        "email_to_meeting_proposal",
        "messenger_to_followup_task",
        "messenger_to_task",
        "document_to_deadline_task",
        "upload_to_project_proposal",
        "invoice_receipt_triage",
        "task_to_calendar_proposal",
    }


def test_inquiry_core_flow_proposes_missing_context_instead_of_blind_writes() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "inquiry.received",
        {
            "tenant": "KUKANILEA",
            "subject": "Neue Anfrage für Projekt Alpha",
            "body": "Kunde fragt nach einem Termin für das Angebot.",
            "inquiry_id": "inq-1",
        },
    )

    assert proposal["flow_id"] == "inquiry_to_task_project_calendar_proposal"
    assert proposal["confirm_points"] == ["create_task", "create_project_proposal", "create_calendar_event"]
    assert proposal["clarifications"]
    steps = {step["action"]: step for step in proposal["steps"]}
    assert steps["create_task"]["mode"] == "confirm"
    assert steps["create_project_proposal"]["mode"] == "propose"
    assert steps["create_calendar_event"]["mode"] == "propose"


def test_execute_blocks_unconfirmed_write_even_if_step_is_misconfigured() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO: Angebot senden",
            "body": "Bitte heute.",
            "email_id": "mail-guard-1",
        },
    )
    proposal_id = proposal["proposal_id"]
    engine._proposals[proposal_id]["steps"][0]["confirm_required"] = False

    result = engine.execute(proposal_id, confirmed=True)
    first = result["results"][0]
    assert first["status"] == "blocked"
    assert first["reason"] == "write_requires_confirm"


def test_email_to_task_requires_confirm_and_audit_points() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO: Angebotsprüfung",
            "body": "Bitte heute prüfen",
            "email_id": "mail-1",
        },
    )

    assert proposal["status"] == "proposal_required"
    assert proposal["flow_id"] == "email_to_task"
    assert proposal["confirm_points"] == ["create_task"]
    assert "mia.proposal.created" in proposal["audit_points"]
    assert "mia.confirm.requested" in proposal["audit_points"]


def test_email_to_task_missing_title_stays_proposal_and_requests_clarification() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO:",
            "body": "Bitte übernehmen",
            "email_id": "mail-2",
        },
    )

    assert proposal["flow_id"] == "email_to_task"
    assert proposal["degradation"] == "proposal_only_without_task_title"
    assert proposal["clarifications"] == ["Welchen konkreten Titel soll die Aufgabe haben?"]
    task_step = proposal["steps"][0]
    assert task_step["mode"] == "propose"
    assert task_step["reason"] == "missing_task_title"


def test_missing_context_stays_in_propose_mode() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "Terminabstimmung",
            "body": "Bitte Termin vorschlagen",
        },
    )

    assert proposal["flow_id"] == "email_to_meeting_proposal"
    calendar_step = [step for step in proposal["steps"] if step["action"] == "create_calendar_event"][0]
    assert calendar_step["mode"] == "propose"
    assert calendar_step["reason"] == "missing_suggested_start"


def test_invoice_flow_offline_degradation_queues_local_review() -> None:
    executed_payloads: list[dict] = []

    def _queue_handler(payload: dict) -> dict:
        executed_payloads.append(payload)
        return {"queued": True}

    engine = MiaFlowEngine(handlers={"queue_local_review": _queue_handler})
    proposal = engine.plan(
        "document.processed",
        {
            "tenant": "KUKANILEA",
            "filename": "rechnung_2026_07.pdf",
            "ocr_text": "Rechnung 2026",
            "search_index_available": False,
            "amount_due": "1290.00",
        },
    )
    assert proposal["degradation"] == "queue_local_review"

    result = engine.execute(proposal["proposal_id"], confirmed=True)
    assert result["status"] == "executed"
    queue_entries = [row for row in result["results"] if row["action"] == "queue_local_review"]
    assert queue_entries
    assert queue_entries[0]["status"] == "executed"
    assert executed_payloads


def test_confirm_gate_blocks_execution_without_explicit_confirmation() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "messenger.received",
        {
            "tenant": "KUKANILEA",
            "thread_id": "chat-9",
            "message": "Bitte nachfassen",
        },
    )

    blocked = engine.execute(proposal["proposal_id"], confirmed=False)
    assert blocked["status"] == "confirmation_required"
    assert engine.audit_log[-1]["event_type"] == "mia.confirm.denied"


def test_step_level_audit_is_emitted_for_email_to_task_execution() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO: Angebot senden",
            "body": "Bitte heute noch.",
            "email_id": "mail-3",
        },
    )

    result = engine.execute(proposal["proposal_id"], confirmed=True)
    assert result["status"] == "executed"
    event_types = [entry["event_type"] for entry in engine.audit_log]
    assert "mia.step.started" in event_types
    assert "mia.step.simulated" in event_types


def test_email_to_task_audit_event_matrix_complete() -> None:
    engine = MiaFlowEngine()
    proposal = engine.plan(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO: Angebot senden",
            "body": "Bitte heute noch.",
            "email_id": "mail-matrix-1",
        },
    )

    plan_event_types = [entry["event_type"] for entry in engine.audit_log]
    for event_type in MIA_FLOW_AUDIT_EVENT_MATRIX["email_to_task"]["plan"]:
        assert event_type in plan_event_types

    executed = engine.execute(proposal["proposal_id"], confirmed=True)
    assert executed["status"] == "executed"

    execute_event_types = [entry["event_type"] for entry in engine.audit_log]
    for event_type in MIA_FLOW_AUDIT_EVENT_MATRIX["email_to_task"]["execute_confirmed"]:
        assert event_type in execute_event_types
