import unittest

from kukanilea.orchestrator.intent import IntentParser


class IntentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = IntentParser()

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


if __name__ == "__main__":
    unittest.main()
