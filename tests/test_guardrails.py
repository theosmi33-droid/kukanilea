from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.guardrails import validate_prompt


def test_validate_prompt_ok():
    assert validate_prompt('Hallo') == (True, 'OK')


def test_validate_prompt_sql_blocked():
    ok, reason = validate_prompt('DROP TABLE users;')
    assert ok is False
    assert 'SQL' in reason
