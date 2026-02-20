from __future__ import annotations

from .openai_compat import OpenAICompatClient


class LMStudioClient(OpenAICompatClient):
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:1234",
        model: str = "local-model",
        api_key: str = "",
        timeout_s: int = 60,
    ) -> None:
        super().__init__(
            provider_name="lmstudio",
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_s=timeout_s,
        )
