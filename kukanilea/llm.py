from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class LLMProvider:
    name: str
    available: bool = True

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        raise NotImplementedError

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        context: Dict[str, Any] | None = None,
    ) -> str:
        _ = context
        prompt = (
            system_prompt
            + "\n"
            + "\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages)
        )
        return self.complete(prompt, temperature=0.0)

    def rewrite_query(self, query: str) -> Dict[str, str]:
        return {"intent": "unknown", "query": query}

    def summarize(self, text: str) -> str:
        return text.strip()[:400]


class MockProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__(name="mock", available=True)

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        _ = temperature
        return f"[mocked] {prompt.strip()[:160]}"

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        context: Dict[str, Any] | None = None,
    ) -> str:
        _ = context
        head = system_prompt.strip()[:80]
        return f"[mocked] {head} :: {len(messages)} messages"

    def rewrite_query(self, query: str) -> Dict[str, str]:
        text = query.lower().strip()
        intent = "unknown"
        if "öffne" in text or "open" in text or "zeige" in text:
            intent = "open_token"
        elif "wer ist" in text or "kunde" in text or "kdnr" in text:
            intent = "customer_lookup"
        elif any(
            k in text for k in ["rechnung", "angebot", "suche", "finde", "search"]
        ):
            intent = "search"
        elif "zusammenfassung" in text or "summary" in text:
            intent = "summary"
        return {"intent": intent, "query": query}


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str) -> None:
        super().__init__(name="ollama", available=False)
        self.host = host.rstrip("/")
        self.model = model
        self.available = self._ping()

    def _ping(self) -> bool:
        try:
            _ = self._get_json("/api/tags", timeout=1.5)
            return True
        except Exception:
            return False

    def _get_json(self, path: str, timeout: float = 4.0) -> Dict[str, Any]:
        req = urllib.request.Request(self.host + path, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(
        self, path: str, payload: Dict[str, Any], timeout: float = 8.0
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.host + path,
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        if not self.available:
            raise RuntimeError("Ollama not available")
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": float(temperature),
        }
        data = self._post_json("/api/generate", payload)
        return str(data.get("response", "")).strip()

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        context: Dict[str, Any] | None = None,
    ) -> str:
        if not self.available:
            raise RuntimeError("Ollama not available")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "stream": False,
        }
        if context:
            payload["context"] = context
        data = self._post_json("/api/chat", payload)
        message = data.get("message", {})
        return str(message.get("content", "")).strip()

    def rewrite_query(self, query: str) -> Dict[str, str]:
        prompt = (
            "Du bist ein lokaler Assistent. Wandle die Nutzeranfrage in JSON um: "
            '{"intent": "...", "query": "..."} mit intent in '
            '["search","open_token","customer_lookup","summary","unknown"]. '
            f"Nutzeranfrage: {query}"
        )
        try:
            raw = self.complete(prompt, temperature=0.0)
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(raw[start : end + 1])
                if isinstance(parsed, dict):
                    return {
                        "intent": str(parsed.get("intent", "unknown")),
                        "query": str(parsed.get("query", query)),
                    }
        except Exception:
            return {"intent": "unknown", "query": query}
        return {"intent": "unknown", "query": query}

    def summarize(self, text: str) -> str:
        prompt = "Fasse den folgenden Text kurz zusammen:\n" + text.strip()[:2000]
        try:
            return self.complete(prompt, temperature=0.2)
        except Exception:
            return text.strip()[:400]


def get_default_provider() -> LLMProvider:
    host = _env("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = _env("OLLAMA_MODEL", "llama3.1")
    enabled = _env("OLLAMA_ENABLED", "0").lower() in {"1", "true", "yes"}
    try:
        if enabled:
            provider = OllamaProvider(host, model)
            if provider.available:
                return provider
    except Exception:
        pass
    return MockProvider()
