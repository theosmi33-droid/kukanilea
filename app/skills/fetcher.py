from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from app.skills.model import SkillFile, SkillImportResult
from app.skills.net import HttpError, http_get_bytes, http_get_text
from app.skills.util import sanitize_skill_name, sha256_bytes

_GITHUB_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _parse_repo(repo_url: str) -> tuple[str, str]:
    source = (repo_url or "").strip()
    if source.startswith("github:"):
        rest = source.split(":", 1)[1]
        parts = [p for p in rest.split("/") if p]
        if len(parts) != 2:
            raise ValueError("invalid_github_source")
        return parts[0], parts[1]

    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise ValueError("unsupported_source")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("invalid_github_source")
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return parts[0], repo


def _resolve_commit(owner: str, repo: str, ref: str) -> str:
    if _GITHUB_SHA_RE.match(ref):
        return ref.lower()
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}"
    try:
        payload = json.loads(http_get_text(url, timeout=20))
        sha = str(payload.get("sha") or "").strip()
        if _GITHUB_SHA_RE.match(sha):
            return sha.lower()
    except Exception:
        pass
    return ref


def fetch_skill_github(
    repo_url: str, skill_name: str, ref: str = "main"
) -> SkillImportResult:
    """Fetch skill files from GitHub raw endpoints without executing content."""
    skill = sanitize_skill_name(skill_name)
    owner, repo = _parse_repo(repo_url)
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/"
    skill_base = f"skills/{skill}"

    files: dict[str, bytes] = {}
    file_meta: list[SkillFile] = []

    def fetch_required(rel_path: str) -> bytes:
        url = raw_base + rel_path
        try:
            data = http_get_bytes(url, timeout=20)
        except HttpError as exc:
            if rel_path.endswith("SKILL.md") and exc.status_code == 404:
                raise ValueError("skill not found") from exc
            raise
        files[rel_path] = data
        file_meta.append(
            SkillFile(path=rel_path, sha256=sha256_bytes(data), bytes_len=len(data))
        )
        return data

    def fetch_optional(rel_path: str) -> bytes | None:
        url = raw_base + rel_path
        try:
            data = http_get_bytes(url, timeout=20)
        except HttpError as exc:
            if exc.status_code == 404:
                return None
            raise
        files[rel_path] = data
        file_meta.append(
            SkillFile(path=rel_path, sha256=sha256_bytes(data), bytes_len=len(data))
        )
        return data

    fetch_required(f"{skill_base}/SKILL.md")
    fetch_optional(f"{skill_base}/skill.json")
    fetch_optional(f"{skill_base}/README.md")

    index_bytes = fetch_optional(f"{skill_base}/resources/index.json")
    if index_bytes is not None:
        try:
            index_payload = json.loads(index_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError("invalid_resources_index") from exc

        resource_list = (
            index_payload
            if isinstance(index_payload, list)
            else index_payload.get("files", [])
        )
        if not isinstance(resource_list, list):
            raise ValueError("invalid_resources_index")
        for item in resource_list:
            rel = str(item).strip()
            if not rel:
                continue
            if rel.startswith("/") or ".." in rel.split("/"):
                raise ValueError("invalid_resource_path")
            fetch_optional(f"{skill_base}/resources/{rel}")

    resolved = _resolve_commit(owner, repo, ref)
    manifest = {
        "name": skill,
        "source_url": f"https://github.com/{owner}/{repo}",
        "ref": ref,
        "resolved_commit": resolved,
        "files": [
            {"path": sf.path, "sha256": sf.sha256, "bytes_len": sf.bytes_len}
            for sf in sorted(file_meta, key=lambda s: s.path)
        ],
    }

    return SkillImportResult(
        name=skill,
        source_url=f"https://github.com/{owner}/{repo}",
        ref=ref,
        resolved_commit=resolved,
        files=files,
        manifest=manifest,
    )
