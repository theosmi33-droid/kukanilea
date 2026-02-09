import unittest

from kukanilea.llm import LLMProvider, MockProvider
from kukanilea.orchestrator.intent import IntentParser


class CountingProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(name="counting", available=True)
        self.rewrite_calls = 0

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        _ = prompt
        _ = temperature
        return ""

    def rewrite_query(self, query: str):
        self.rewrite_calls += 1
        return {"intent": "unknown", "query": query}


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = IntentParser(MockProvider())

    def test_open_token(self):
        result = self.parser.parse("öffne abcdef1234567890abcd")
        self.assertEqual(result.intent, "open_token")

    def test_search_intent(self):
        result = self.parser.parse("suche rechnung kdnr 1234")
        self.assertEqual(result.intent, "search")

    def test_review_intent(self):
        result = self.parser.parse("bitte review für die ablage")
        self.assertEqual(result.intent, "review")

    def test_weather_intent(self):
        result = self.parser.parse("wetter in berlin")
        self.assertEqual(result.intent, "weather")

    def test_short_queries(self):
        self.assertEqual(self.parser.parse("rechnung").intent, "search")
        self.assertEqual(self.parser.parse("wer ist 12393").intent, "customer_lookup")
        self.assertEqual(self.parser.parse("öffne abcdef1234567890abcd").intent, "open_token")
        self.assertEqual(self.parser.parse("test").intent, "search")
        self.assertEqual(self.parser.parse("warmbrunn").intent, "search")

    def test_safe_mode_skips_llm(self):
        provider = CountingProvider()
        parser = IntentParser(provider)
        result = parser.parse("kannst du mir helfen bitte", allow_llm=False)
        self.assertEqual(result.intent, "unknown")
        self.assertEqual(provider.rewrite_calls, 0)

    def test_llm_used_when_allowed(self):
        provider = CountingProvider()
        parser = IntentParser(provider)
        parser.parse("kannst du mir helfen bitte", allow_llm=True)
        self.assertEqual(provider.rewrite_calls, 1)


if __name__ == "__main__":
    unittest.main()
