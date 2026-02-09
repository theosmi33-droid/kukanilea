from __future__ import annotations

import re
from datetime import datetime, timedelta
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


def _parse_doc_date(doc_date: str) -> datetime | None:
    if not doc_date:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(doc_date, fmt)
        except ValueError:
            continue
    return None


def _score_hit(query: str, hit: Dict[str, Any]) -> float:
    score = 0.0
    q = query.lower()
    file_name = str(hit.get("file_name", "")).lower()
    doctype = str(hit.get("doctype", "")).lower()
    doc_date = str(hit.get("doc_date", ""))
    kdnr = str(hit.get("kdnr", "")).lower()

    if q and q in file_name:
        score += 3.0
    if q and q in doctype:
        score += 2.0
    if kdnr and q == kdnr:
        score += 4.0
    if hit.get("kdnr"):
        score += 1.0
    if fuzz is not None:
        score += (fuzz.partial_ratio(q, file_name) / 100.0) * 2.0
        if doctype:
            score += (fuzz.partial_ratio(q, doctype) / 100.0) * 1.5
    if doc_date:
        parsed = _parse_doc_date(doc_date)
        if parsed:
            days = (datetime.utcnow() - parsed).days
            if days <= 90:
                score += 1.2
            elif days <= 365:
                score += 0.6
        else:
            score += 0.2
    return score


class SearchAgent(BaseAgent):
    name = "search"
    required_role = "READONLY"
    scope = "search"
    tools = ["search_docs", "open_token"]

    def __init__(self, core_module) -> None:
        self.core = core_module

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "search"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        results, suggestions = self.search(message, context, limit=8)

        if not results:
            if suggestions:
                return AgentResult(
                    text=f"Keine Treffer. Meintest du: {', '.join(suggestions)}?",
                    suggestions=suggestions,
                    data={"did_you_mean": suggestions},
                )
            return AgentResult(text="Keine Treffer gefunden.", suggestions=["suche rechnung", "suche angebot"])

        ranked: List[SearchHit] = []
        for row in results:
            ranked.append(SearchHit(score=_score_hit(message, row), row=row))
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
        return AgentResult(
            text=f"Ich habe {len(lines)} Treffer gefunden:\n{summary}",
            actions=actions,
            data={"results": results},
            suggestions=["öffne <token>", "suche weiteres dokument"],
        )

    def search(self, message: str, context: AgentContext, limit: int = 8) -> tuple[List[Dict[str, Any]], List[str]]:
        query = message.strip()
        kdnr = context.kdnr
        kdnr_match = re.search(r"kdnr\s*(\d{3,})", query, re.IGNORECASE)
        if kdnr_match:
            kdnr = kdnr_match.group(1)
        if re.fullmatch(r"\d{3,6}", query):
            kdnr = query

        results: List[Dict[str, Any]] = []
        if callable(getattr(self.core, "assistant_search", None)):
            results = self.core.assistant_search(
                query=query,
                kdnr=kdnr,
                limit=limit,
                role=context.role,
                tenant_id=context.tenant_id,
            )

        if not results:
            results = self._fs_scan(query, context)

        suggestions: List[str] = []
        if not results:
            suggestions = self._did_you_mean(query, context)
        return results, suggestions

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
        if callable(getattr(self.core, "assistant_suggest", None)):
            return self.core.assistant_suggest(query=query, tenant_id=context.tenant_id)
        base = getattr(self.core, "BASE_PATH", None)
        if base is None or process is None or fuzz is None:
            return []
        tenant_root = Path(base) / (context.tenant_id or "")
        if not tenant_root.exists():
            return []
        candidates = [p.name for p in tenant_root.glob("*") if p.is_dir()]
        matches = process.extract(query, candidates, scorer=fuzz.partial_ratio, limit=3)
        return [m[0] for m in matches if m[1] >= 70]
