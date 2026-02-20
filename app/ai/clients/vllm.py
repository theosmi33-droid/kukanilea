from __future__ import annotations

from .openai_compat import OpenAICompatClient


class VLLMClient(OpenAICompatClient):
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8000",
        model: str = "meta-llama/Llama-3.1-8B-Instruct",
        api_key: str = "",
        timeout_s: int = 60,
    ) -> None:
        super().__init__(
            provider_name="vllm",
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_s=timeout_s,
        )
