from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("kukanilea.validator")

T = TypeVar("T", bound=BaseModel)


class AIResponseValidator:
    """
    Validates JSON responses from Ollama against Pydantic models.
    Ensures 100% type safety for database operations.
    """

    @staticmethod
    def validate(response_text: str, model: Type[T]) -> Optional[T]:
        """
        Parses JSON from response_text and validates it against the provided Pydantic model.
        Returns the validated model instance or None if validation fails.
        """
        if not response_text:
            return None

        try:
            # Clean response text (Ollama might wrap JSON in markdown blocks)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]

            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]

            cleaned_text = cleaned_text.strip()

            # Attempt to find the first '{' and last '}' if parsing fails initially
            # to handle conversational filler around the JSON.
            try:
                data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                start_idx = cleaned_text.find("{")
                end_idx = cleaned_text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    cleaned_text = cleaned_text[start_idx : end_idx + 1]
                    data = json.loads(cleaned_text)
                else:
                    raise

            return model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"AI Response Validation failed: {e}")
            logger.debug(f"Raw response: {response_text}")
            return None
