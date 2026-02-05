import unittest

from kukanilea.llm import MockProvider
from kukanilea.orchestrator.intent import IntentParser


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


if __name__ == "__main__":
    unittest.main()
