import unittest
from pathlib import Path

from app.agents.base import AgentContext
from app.agents.orchestrator import MessengerAgent


class TestMessengerAgent(unittest.TestCase):
    def setUp(self):
        self.agent = MessengerAgent()

    def test_can_handle_tokens(self):
        self.assertTrue(self.agent.can_handle("unknown", "Wie ist der Status bei Telegram?"))
        self.assertTrue(self.agent.can_handle("unknown", "Schicke eine Nachricht an @kukanilea"))
        self.assertFalse(self.agent.can_handle("unknown", "Suche Rechnung"))

    def test_extract_provider(self):
        self.assertEqual(self.agent._extract_provider("Telegram message"), "telegram")
        self.assertEqual(self.agent._extract_provider("WhatsApp call"), "whatsapp")
        self.assertEqual(self.agent._extract_provider("Interner Chat"), "internal")

    def test_crm_match_phone(self):
        match = self.agent._crm_match_hint("Bitte anrufen: +49 170 1234567")
        self.assertEqual(match["source"], "phone")
        self.assertIn("+49 170 1234567", match["display"])

    def test_handle_basic(self):
        context = AgentContext(tenant_id="test-tenant", user="test-user", role="USER")
        # No DB setup here, so stored will be False
        result = self.agent.handle("Schicke eine Nachricht über Telegram", "messenger", context)
        self.assertEqual(result.data["hub"]["provider"], "telegram")
        self.assertTrue(len(result.data["hub"]["proposals"]) > 0)
        self.assertIn("messenger_send", [p["type"] for p in result.data["hub"]["proposals"]])

    def test_invoice_extract_due_contract_contains_untrusted_guard(self):
        source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
        self.assertIn('"invoice_extract_due"', source)
        self.assertIn('_extract_untrusted_text(p, "invoice_due_date")', source)

    def test_manager_agent_contract_removes_neutral_prompt_injection_downgrade(self):
        source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
        self.assertNotIn("if injection_matches and neutral_context and not action_context:", source)

    def test_manager_agent_contract_keeps_missing_context_clarification_gate(self):
        source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
        self.assertIn('reason="missing_context"', source)
        self.assertIn("manager_agent.needs_clarification", source)

    def test_cross_tool_flows_contract_avoids_traceback_storage(self):
        source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
        self.assertNotIn("traceback.format_exc()", source)

    def test_project_logic_contract_adds_missing_team_task_project_columns(self):
        source = Path("app/modules/projects/logic.py").read_text(encoding="utf-8")
        self.assertIn("PRAGMA table_info(team_tasks)", source)
        self.assertIn("ALTER TABLE team_tasks ADD COLUMN", source)

if __name__ == "__main__":
    unittest.main()
