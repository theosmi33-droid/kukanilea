from __future__ import annotations

from pathlib import Path

from kukanilea.agents import AgentContext
from kukanilea.agents.search import SearchAgent
from app import web


class DummyCore:
    def __init__(self, base_path: Path) -> None:
        self.BASE_PATH = base_path

    def assistant_search(self, query, kdnr="", limit=8, role="ADMIN", tenant_id=""):
        return []

    def assistant_suggest(self, query, tenant_id="", limit=3):
        return ["Gerda"] if "gerd" in query.lower() else []


def test_search_fallback_and_fuzzy(tmp_path):
    core = DummyCore(tmp_path)
    agent = SearchAgent(core)
    ctx = AgentContext(tenant_id="KUKANILEA", user="dev", role="ADMIN")
    result = agent.handle("suche angebot von gerd", "search", ctx)
    assert "Meintest du" in result.text


def test_dev_db_switch_allowlist(tmp_path):
    instance_dir = (web.Config.BASE_DIR / "instance").resolve()
    instance_dir.mkdir(parents=True, exist_ok=True)
    allowed_file = instance_dir / "kukanilea_test.db"
    allowed_file.write_text("")
    blocked = tmp_path / "blocked.db"
    blocked.write_text("")

    assert web._is_allowlisted_path(allowed_file) is True
    assert web._is_allowlisted_path(blocked) is False
