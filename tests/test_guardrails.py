import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.guardrails import requires_confirm_for_prompt, validate_prompt


def test_validate_prompt_ok():
    assert validate_prompt('Hallo') == (True, 'OK')


def test_validate_prompt_sql_blocked():
    ok, reason = validate_prompt('DROP TABLE users;')
    assert ok is False
    assert 'SQL' in reason


def test_write_like_prompt_requires_confirm():
    assert requires_confirm_for_prompt('please create a task') is True


def test_uncertain_prompt_requires_confirm_by_default():
    assert requires_confirm_for_prompt('maybe do whatever seems best') is True
