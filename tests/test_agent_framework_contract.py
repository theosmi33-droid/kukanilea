from __future__ import annotations

from pathlib import Path

DOCS_DIR = Path("docs/agents")
CONFIG_DOC = Path("app/agents/config/AGENTS.md")
TODO_PATH = Path("tasks/todo.md")
LESSONS_PATH = Path("tasks/lessons.md")

EXPECTED_DOC_FILES = {
    "AGENTS.md",
    "BOOT.md",
    "HEARTBEAT.md",
    "IDENTITY.md",
    "MEMORY.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
}

EXPECTED_ORCHESTRATORS = {
    "app/agents/orchestrators/router.py",
    "app/agents/orchestrators/scheduler.py",
    "app/agents/orchestrators/triage.py",
}

EXPECTED_WORKERS = {
    "app/agents/workers/auth_bot.py",
    "app/agents/workers/db_bot.py",
    "app/agents/workers/sec_bot.py",
}


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path}"
    return path.read_text(encoding="utf-8")


def test_docs_agents_has_required_contract_files() -> None:
    actual = {p.name for p in DOCS_DIR.glob("*.md")}
    assert EXPECTED_DOC_FILES.issubset(actual)


def test_agents_doc_declares_orchestrator_roles() -> None:
    text = _read(DOCS_DIR / "AGENTS.md")
    assert "ROUTER" in text
    assert "SCHEDULER" in text
    assert "TRIAGE" in text


def test_agents_doc_declares_worker_and_safeguard_roles() -> None:
    text = _read(DOCS_DIR / "AGENTS.md")
    assert "AUTH_BOT" in text
    assert "SEC_BOT" in text
    assert "CANARY" in text
    assert "OBSERVER" in text


def test_agents_doc_enforces_approval_gates_and_retention_policy() -> None:
    text = _read(DOCS_DIR / "AGENTS.md")
    assert "GATED WRITES" in text
    assert "60-DAY RETENTION" in text


def test_agent_config_document_exists_and_mentions_cleanup_job() -> None:
    text = _read(CONFIG_DOC)
    assert "OpenClaw" in text
    assert "scripts/ops/memory_cleanup.py" in text


def test_expected_orchestrator_files_exist() -> None:
    for rel in EXPECTED_ORCHESTRATORS:
        assert Path(rel).exists(), rel


def test_expected_worker_files_exist() -> None:
    for rel in EXPECTED_WORKERS:
        assert Path(rel).exists(), rel


def test_agent_task_docs_exist() -> None:
    assert TODO_PATH.exists()
    assert LESSONS_PATH.exists()
