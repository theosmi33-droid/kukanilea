from __future__ import annotations

import json

import pytest

from app.skills import fetcher
from app.skills.net import HttpError


def test_fetch_skill_github_requires_skill_md(monkeypatch) -> None:
    def fake_get_bytes(url: str, timeout: int = 20) -> bytes:
        del timeout
        raise HttpError(f"http_error:404 {url}", 404)

    monkeypatch.setattr(fetcher, "http_get_bytes", fake_get_bytes)

    with pytest.raises(ValueError, match="skill not found"):
        fetcher.fetch_skill_github("https://github.com/acme/repo", "demo", ref="main")


def test_fetch_skill_github_with_sha_ref_builds_manifest(monkeypatch) -> None:
    sha_ref = "a" * 40
    got_urls: list[str] = []

    def fake_get_bytes(url: str, timeout: int = 20) -> bytes:
        del timeout
        got_urls.append(url)
        if url.endswith("skills/demo/SKILL.md"):
            return b"# Skill Demo\n"
        if url.endswith("skills/demo/skill.json"):
            return b'{"name":"demo"}'
        if url.endswith("skills/demo/README.md"):
            return b"readme"
        if url.endswith("skills/demo/resources/index.json"):
            return b'{"files":["a.txt"]}'
        if url.endswith("skills/demo/resources/a.txt"):
            return b"alpha"
        raise HttpError(f"http_error:404 {url}", 404)

    monkeypatch.setattr(fetcher, "http_get_bytes", fake_get_bytes)

    result = fetcher.fetch_skill_github(
        "https://github.com/acme/repo", "demo", ref=sha_ref
    )
    assert result.name == "demo"
    assert result.ref == sha_ref
    assert result.resolved_commit == sha_ref
    assert "skills/demo/SKILL.md" in result.files
    assert any(item["path"].endswith("SKILL.md") for item in result.manifest["files"])
    assert any(
        url.startswith("https://raw.githubusercontent.com/acme/repo/")
        for url in got_urls
    )


def test_fetch_skill_github_resolves_non_sha_ref(monkeypatch) -> None:
    resolved_sha = "b" * 40

    def fake_get_text(url: str, timeout: int = 20) -> str:
        del timeout
        assert "/commits/main" in url
        return json.dumps({"sha": resolved_sha})

    def fake_get_bytes(url: str, timeout: int = 20) -> bytes:
        del timeout
        if url.endswith("skills/demo/SKILL.md"):
            return b"content"
        raise HttpError(f"http_error:404 {url}", 404)

    monkeypatch.setattr(fetcher, "http_get_text", fake_get_text)
    monkeypatch.setattr(fetcher, "http_get_bytes", fake_get_bytes)

    result = fetcher.fetch_skill_github("github:acme/repo", "demo", ref="main")
    assert result.resolved_commit == resolved_sha
