from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.memory_store import MemoryManager
from app.config import Config

logger = logging.getLogger("kukanilea.ocr_corrector")

class OCRCorrector:
    """
    Leverages past user corrections stored in semantic memory
    to improve current document analysis.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.memory = MemoryManager(str(Config.AUTH_DB))

    def get_correction_context(self, text: str, limit: int = 2) -> str:
        """
        Retrieves relevant past corrections and formats them as Few-Shot examples.
        """
        if not text:
            return ""
            
        try:
            # Search for similar documents that were corrected
            hits = self.memory.retrieve_context(self.tenant_id, text[:1000], limit=10)
            
            corrections = [
                h for h in hits 
                if h.get("metadata", {}).get("type") == "ocr_correction"
            ]
            
            if not corrections:
                return ""
                
            context_lines = ["Hier sind Beispiele für frühere Korrekturen bei ähnlichen Dokumenten:"]
            for h in corrections[:limit]:
                content = h.get("content", "")
                if "KORREKTUR-WISSEN:" in content:
                    knowledge = content.split("Kontext-Auszug:")[0].strip()
                    context_lines.append(knowledge)
            
            return "\n".join(context_lines)
            
        except Exception as e:
            logger.warning(f"Failed to fetch correction context: {e}")
            return ""

    def apply_corrections_to_prompt(self, base_prompt: str, text: str) -> str:
        """
        Injects correction context into the AI refinement prompt.
        """
        wisdom = self.get_correction_context(text)
        if wisdom:
            return f"{wisdom}\n\n{base_prompt}"
        return base_prompt
