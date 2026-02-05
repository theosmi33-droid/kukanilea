from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List

from .base import AgentContext, AgentResult, BaseAgent

try:
    from rapidfuzz import process, fuzz  # type: ignore
except Exception:
    process = None  # type: ignore
    fuzz = None  # type: ignore


@dataclass
class SearchHit:
    score: float
    row: Dict[str, Any]


def _score_hit(query: str, hit: Dict[str, Any]) -> float:
    score = 0.0
    q = query.lower()
    file_name = str(hit.get("file_name", "")).lower()
    doctype = str(hit.get("doctype", "")).lower()
    doc_date = str(hit.get("doc_date", ""))

    if q and q in file_name:
        score += 3.0
    if q and q in doctype:
        score += 2.0
    if doc_date:
        score += 0.5
    if hit.get("kdnr"):
        score += 1.0
    return score


class SearchAgent(BaseAgent):
    name = "search"
    required_role = "READONLY"
    scope = "search"
    tools = ["search"]

    def __init__(self, core_module) -> None:
        self.core = core_module

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in {"search", "customer_lookup"}

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        query = message.strip()
        kdnr = context.kdnr
        kdnr_match = re.search(r"kdnr\s*(\d{3,})", query, re.IGNORECASE)
        if kdnr_match:
            kdnr = kdnr_match.group(1)
        if re.fullmatch(r"\d{3,6}", query):
            kdnr = query

        results = []
        if callable(getattr(self.core, "assistant_search", None)):
            results = self.core.assistant_search(query=query, kdnr=kdnr, limit=8, role=context.role, tenant_id=context.tenant_id)

        if not results:
            results = self._fs_scan(query, context)

        if not results:
            suggestion = self._did_you_mean(query, context)
            if suggestion:
                return AgentResult(text=f"Keine Treffer. Meintest du: {', '.join(suggestion)}?")
            return AgentResult(text="Keine Treffer gefunden.")

        ranked: List[SearchHit] = []
        for row in results:
            ranked.append(SearchHit(score=_score_hit(query, row), row=row))
        ranked.sort(key=lambda r: r.score, reverse=True)

        actions = []
        lines = []
        for hit in ranked:
            row = hit.row
            token = str(row.get("doc_id", ""))
            line = f"{row.get('doctype','')} {row.get('kdnr','')} {row.get('doc_date','')} {row.get('file_name','')}"
            lines.append(line.strip())
            if token:
                actions.append({"type": "open_token", "token": token})

        if not lines:
            return AgentResult(text="Keine Treffer gefunden.")

        summary = "\n".join(f"• {ln}" for ln in lines)
        return AgentResult(text=f"Ich habe {len(lines)} Treffer gefunden:\n{summary}", actions=actions, data={"results": results})

    def _fs_scan(self, query: str, context: AgentContext) -> List[Dict[str, Any]]:
        base = getattr(self.core, "BASE_PATH", None)
        if base is None:
            return []
        tenant_root = Path(base) / (context.tenant_id or "")
        if not tenant_root.exists():
            return []
        tokens = [t for t in re.split(r"\s+", query.lower()) if t]
        hits = []
        for fp in tenant_root.rglob("*"):
            if not fp.is_file():
                continue
            hay = fp.name.lower()
            if tokens and all(t in hay for t in tokens[:3]):
                hits.append(
                    {
                        "doc_id": fp.name,
                        "kdnr": "",
                        "doctype": "",
                        "doc_date": "",
                        "file_name": fp.name,
                        "file_path": str(fp),
                        "preview": "",
                    }
                )
            if len(hits) >= 5:
                break
        return hits

    def _did_you_mean(self, query: str, context: AgentContext) -> List[str]:
        base = getattr(self.core, "BASE_PATH", None)
        if base is None or process is None or fuzz is None:
            return []
        tenant_root = Path(base) / (context.tenant_id or "")
        if not tenant_root.exists():
            return []
        candidates = [p.name for p in tenant_root.glob("*") if p.is_dir()]
        matches = process.extract(query, candidates, scorer=fuzz.partial_ratio, limit=3)
        return [m[0] for m in matches if m[1] >= 70]
