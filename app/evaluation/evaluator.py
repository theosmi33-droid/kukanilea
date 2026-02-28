from __future__ import annotations

from typing import Any, Callable, Dict

from app.evaluation.metrics import Metrics


class Evaluator:
    """
    High-level evaluation logic for system performance and quality.
    """

    def __init__(self):
        self.metrics = Metrics()

    def evaluate(self, fn: Callable, *args, **kwargs) -> Dict[str, Any]:
        result, duration = self.metrics.measure(fn, *args, **kwargs)
        return {"result": result, "duration_seconds": duration}
