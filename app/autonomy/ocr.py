from __future__ import annotations

import logging
import shutil

logger = logging.getLogger("kukanilea")


def resolve_tesseract_path() -> str | None:
    # No hardcoded paths - use shutil.which to find binary in PATH
    tesseract_bin = shutil.which("tesseract")

    if not tesseract_bin:
        logger.warning(
            "Tesseract binary not found in PATH. OCR features will be disabled (Degraded Mode)."
        )
        return None

    return tesseract_bin


TESSERACT_CMD = resolve_tesseract_path()
OCR_AVAILABLE = TESSERACT_CMD is not None


def get_ocr_status():
    return {"available": OCR_AVAILABLE, "path": TESSERACT_CMD}
