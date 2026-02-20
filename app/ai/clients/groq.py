from __future__ import annotations

from .openai_compat import OpenAICompatClient


class GroqClient(OpenAICompatClient):
    def __init__(
        self,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "llama-3.3-70b-versatile",
        api_key: str = "",
        timeout_s: int = 30,
    ) -> None:
        super().__init__(
            provider_name="groq",
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_s=timeout_s,
        )
