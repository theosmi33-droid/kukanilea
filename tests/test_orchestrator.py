import unittest

from kukanilea.agents import AgentContext
from kukanilea.llm import MockProvider
from kukanilea.orchestrator import Orchestrator


class DummyCore:
    def assistant_search(self, query, kdnr="", limit=8, role="ADMIN", tenant_id=""):
        return [
            {
                "doc_id": "abc123def456",
                "token": "abc123def456",
                "kdnr": kdnr or "12393",
                "doctype": "RECHNUNG",
                "doc_date": "2024-06-01",
                "file_name": "rechnung.pdf",
                "file_path": "/tmp/rechnung.pdf",
                "preview": "...",
            }
        ]


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(DummyCore(), llm_provider=MockProvider())
        self.context = AgentContext(tenant_id="KUKANILEA", user="dev", role="ADMIN")

    def test_search_intent(self):
        result = self.orch.handle("suche rechnung von gerd warmbrunn", self.context)
        self.assertIn("Treffer", result.text)
        self.assertTrue(result.actions)

    def test_open_token(self):
        ctx = AgentContext(
            tenant_id="KUKANILEA", user="dev", role="ADMIN", token="abc123def456"
        )
        result = self.orch.handle("öffne abc123def456", ctx)
        self.assertEqual(result.actions[0]["type"], "open_token")

    def test_customer_lookup(self):
        result = self.orch.handle("kunde mit kdnr 12393", self.context)
        self.assertIn("Kunde", result.text)


if __name__ == "__main__":
    unittest.main()
