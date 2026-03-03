from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from app.agents.memory_store import MemoryManager
from app.config import Config
from app.core.upload_pipeline import (
    apply_layout_corrections,
    compute_layout_hash,
    load_layout_corrections,
)

logger = logging.getLogger("kukanilea.ocr_corrector")


class OCRCorrector:
    """
    Leverages deterministic layout corrections + semantic memories
    to avoid repeating known extraction mistakes.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id or "").strip() or "default"
        self.memory = MemoryManager(str(Config.AUTH_DB))

    def _fewshot_from_memory(self, text: str, limit: int = 2) -> List[str]:
        if not text:
            return []
        try:
            hits = self.memory.retrieve_context(self.tenant_id, text[:1200], limit=max(4, limit * 3))
            if not hits:
                return []
            
            corrections = [h for h in hits if h.get("metadata", {}).get("type") == "ocr_correction"]
            lines: List[str] = []
            for hit in corrections:
                content = str(hit.get("content", "") or "").strip()
                if not content:
                    continue
                
                found_fewshot = False
                for row in content.splitlines():
                    row = row.strip()
                    if row.startswith("FEWSHOT|"):
                        lines.append(row)
                        found_fewshot = True
                
                if "KORREKTUR-WISSEN:" in content and not found_fewshot:
                    # Legacy fallback parsing
                    parts = content.split("Kontext-Auszug:", 1)
                    legacy = parts[0].replace("KORREKTUR-WISSEN:", "").strip()
                    if legacy:
                        lines.append(f"LEGACY|{legacy}")
                
                if len(lines) >= limit:
                    break
                    
            return lines[:limit]
        except Exception as exc:
            logger.warning("Failed loading semantic correction context: %s", exc)
            return []

    def apply_corrections(self, extracted: Dict[str, Any], text: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Applies known corrections for the same layout hash.
        Returns (updated_fields, provenance) where provenance marks auto-learned values.
        """
        layout_hash = compute_layout_hash(text)
        corrections = load_layout_corrections(self.tenant_id, layout_hash)
        updated, provenance = apply_layout_corrections(extracted, corrections)
        if provenance:
            updated["layout_hash"] = layout_hash
            updated["correction_source"] = "aus frueherer Korrektur"
            updated["corrections_applied"] = dict(provenance)
        return updated, provenance

    def get_correction_context(self, text: str, limit: int = 2) -> str:
        """
        Builds prompt context from deterministic layout corrections first,
        then semantic few-shot records.
        """
        layout_hash = compute_layout_hash(text)
        layout_corrections = load_layout_corrections(self.tenant_id, layout_hash)
        fewshot = self._fewshot_from_memory(text=text, limit=limit)

        if not layout_corrections and not fewshot:
            return ""

        lines = [
            "WISSENSINJEKTION OCR:",
            "Hier sind Beispiele für frühere Korrekturen bei ähnlichen Dokumenten:",
            "Wenn ein Feld aus frueherer Korrektur vorhanden ist, priorisieren Sie diesen Wert.",
        ]
        if layout_corrections:
            lines.append(f"LAYOUT_HASH: {layout_hash}")
            for field, value in sorted(layout_corrections.items()):
                lines.append(f"AUS_FRUEHERER_KORREKTUR|field={field}|value={value}")

        if fewshot:
            lines.append("SEMANIC_FEWSHOT:")
            for item in fewshot:
                if item.startswith("LEGACY|"):
                    lines.append(item.split("LEGACY|", 1)[1])
                else:
                    lines.append(item)

        return "\n".join(lines)

    def apply_corrections_to_prompt(self, base_prompt: str, text: str) -> str:
        """
        Injects correction context into the AI refinement prompt.
        """
        wisdom = self.get_correction_context(text)
        if wisdom:
            return f"{wisdom}\n\n{base_prompt}"
        return base_prompt
