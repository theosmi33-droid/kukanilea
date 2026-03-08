import unittest
from unittest.mock import Mock
from app.agents.orchestrator import MessengerAgent
from app.agents.base import AgentContext

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

    def test_agentic_loop_defers_allowlisted_actions(self):
        context = AgentContext(tenant_id="test-tenant", user="test-user", role="USER")
        self.agent.planner = Mock()
        self.agent.executor = Mock()
        self.agent.planner.plan.side_effect = [
            {"tool": "search_docs", "params": {"query": "Q1"}, "thought": "Suche Kontext"},
            {"tool": "final_answer", "params": {"answer": "done"}, "thought": "fertig"},
        ]

        result = self.agent.handle("@kukanilea bitte suche Q1 Umsatztrend im Archiv", "messenger", context)

        self.agent.executor.execute.assert_not_called()
        self.assertEqual(result.actions, [{"type": "search_docs", "query": "Q1"}])
        self.assertEqual(result.data["hub"]["react_trace"][0]["observation"]["status"], "deferred")

    def test_agentic_loop_blocks_non_allowlisted_tool_execution(self):
        context = AgentContext(tenant_id="test-tenant", user="test-user", role="USER")
        self.agent.planner = Mock()
        self.agent.executor = Mock()
        self.agent.planner.plan.return_value = {
            "tool": "filesystem_list",
            "params": {"path": "."},
            "thought": "Dateien anzeigen",
        }

        result = self.agent.handle("@kukanilea list files please now", "messenger", context)

        self.agent.executor.execute.assert_not_called()
        self.assertEqual(result.actions, [])
        self.assertEqual(result.data["hub"]["react_trace"][0]["observation"]["status"], "blocked")

if __name__ == "__main__":
    unittest.main()
