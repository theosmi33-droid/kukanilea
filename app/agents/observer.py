from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type, TypeVar

from pydantic import BaseModel

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.validator import AIResponseValidator

logger = logging.getLogger("kukanilea.agents.observer")

T = TypeVar("T", bound=BaseModel)


class ObserverAgent(BaseAgent):
    """
    The Sentinel. Monitors AI outputs, system limits, and ensures type safety.
    Can issue a Veto if validation fails and triggers a deterministic retry.
    """

    name = "observer"
    required_role = "OPERATOR"
    scope = "security"

    def veto_and_retry(
        self,
        prompt: str,
        model: Type[T],
        generator: Callable[[str, float], Optional[str]],
    ) -> Optional[T]:
        """
        Attempts to generate and validate a response.
        If validation fails, issues a veto and retries with Temperature 0.0.
        """
        # Initial attempt (e.g. with default temperature)
        response = generator(prompt, 0.7)
        validated = AIResponseValidator.validate(response or "", model)

        if validated:
            return validated

        logger.warning(
            "Observer issued VETO for failed validation. Retrying with Temp 0.0..."
        )

        # Deterministic Retry
        response = generator(prompt, 0.0)
        validated = AIResponseValidator.validate(response or "", model)

        if validated:
            logger.info("Deterministic retry successful.")
            return validated

        logger.error("Observer VETO final: Deterministic retry also failed validation.")
        return None
