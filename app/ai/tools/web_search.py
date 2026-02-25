"""
app/ai/tools/web_search.py
Tool für die KUKANILEA Agentic AI, um Echtzeit-Informationen aus dem Internet zu laden.
Nutzt DuckDuckGo (lokal/privat) oder Tavily (strukturiert).
"""

import os
import logging
from typing import List, Dict, Any
from duckduckgo_search import DDGS

logger = logging.getLogger("kukanilea.tools.search")

def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Sucht im Internet nach der angegebenen Query und gibt Titel, Link und Snippet zurück.
    Dieses Tool wird vom Orchestrator gerufen, wenn lokales Wissen nicht ausreicht.
    """
    logger.info(f"Agentic Search: {query}")
    
    results = []
    try:
        # Prüfung ob Internetzugang erlaubt ist (Sicherheitsschranke)
        if os.environ.get("KUKANILEA_ALLOW_INTERNET", "0") != "1":
            return [{"error": "Internetzugang ist in den Einstellungen deaktiviert."}]

        with DDGS() as ddgs:
            ddgs_generator = ddgs.text(query, region='de-de', safesearch='on', timelimit='y', max_results=max_results)
            for r in ddgs_generator:
                results.append({
                    "title": r.get("title", ""),
                    "link": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
                
        if not results:
            return [{"message": "Keine relevanten Ergebnisse im Internet gefunden."}]
            
        return results
    except Exception as e:
        logger.error(f"Search Tool Fehler: {e}")
        return [{"error": f"Websuche fehlgeschlagen: {str(e)}"}]

def get_tool_metadata():
    """Definition für das LLM-Toolbinding."""
    return {
        "name": "web_search",
        "description": "Sucht im Internet nach aktuellen Informationen (Preise, Normen, Nachrichten), wenn das lokale Wissen nicht ausreicht.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Die Suchanfrage für die Websuche (am besten auf Deutsch)."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximale Anzahl der Ergebnisse (Standard: 5)."
                }
            },
            "required": ["query"]
        }
    }
